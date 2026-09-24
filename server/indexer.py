"""Watches configured folders, hashes files, extracts text, and feeds the
tagging pipeline. Watchdog import is isolated so this still works (in a
degraded, poll-free mode) if watchdog is unavailable."""
import hashlib
import os
import threading
import time
from pathlib import Path

from . import config, db, events, tagging
from .textextract import extract_text

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAVE_WATCHDOG = True
except ImportError:
    HAVE_WATCHDOG = False
    Observer = None
    FileSystemEventHandler = object


def hash_file(path: Path, chunk_size=1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _should_index(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in config.SUPPORTED_EXTRACT_EXTENSIONS.union({
        ext for ext in (".exe", ".msi", ".zip", ".png", ".jpg", ".jpeg")
    })


class Indexer:
    def __init__(self, folders):
        self.folders = [Path(f) for f in folders]
        self._observers = []
        self._scan_thread = None
        self.status = {"scanning": False, "total": 0, "done": 0}
        self._lock = threading.Lock()

    # --- lifecycle -------------------------------------------------
    def start(self):
        self._scan_thread = threading.Thread(target=self.initial_scan, daemon=True)
        self._scan_thread.start()
        if HAVE_WATCHDOG:
            for folder in self.folders:
                if not folder.exists():
                    continue
                handler = _Handler(self)
                observer = Observer()
                observer.schedule(handler, str(folder), recursive=True)
                observer.start()
                self._observers.append(observer)

    def stop(self):
        for observer in self._observers:
            observer.stop()
            observer.join(timeout=2)

    # --- scanning ----------------------------------------------------
    def initial_scan(self):
        all_files = []
        for folder in self.folders:
            if not folder.exists():
                continue
            for root, _dirs, filenames in os.walk(folder):
                for name in filenames:
                    path = Path(root) / name
                    if _should_index(path):
                        all_files.append(path)

        with self._lock:
            self.status = {"scanning": True, "total": len(all_files), "done": 0}
        events.publish("index-progress", self.status)

        for path in all_files:
            try:
                self.index_file(path)
            except Exception:
                pass
            with self._lock:
                self.status["done"] += 1
            events.publish("index-progress", self.status)

        with self._lock:
            self.status["scanning"] = False
        events.publish("index-progress", self.status)

    def index_file(self, path: Path):
        if not path.exists() or not path.is_file():
            return None
        try:
            stat = path.stat()
        except OSError:
            return None

        file_hash = hash_file(path)
        ext = path.suffix.lower()

        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO files (hash, path, name, ext, size, ctime, mtime, deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)
                   ON CONFLICT(path) DO UPDATE SET
                     hash=excluded.hash, name=excluded.name, ext=excluded.ext,
                     size=excluded.size, ctime=excluded.ctime, mtime=excluded.mtime,
                     deleted=0, deleted_at=NULL""",
                (file_hash, str(path), path.name, ext, stat.st_size, stat.st_ctime, stat.st_mtime),
            )
            cur.execute("SELECT id FROM files WHERE path=?", (str(path),))
            file_id = cur.fetchone()["id"]

        self._restore_retained_tags(file_hash)

        text_content = ""
        if ext in config.SUPPORTED_EXTRACT_EXTENSIONS:
            text_content = extract_text(path)

        tagging.tag_from_rules(path.name, ext, text_content, file_hash)
        tagging.tag_from_calendar(file_hash, stat.st_ctime)
        tagging.tag_from_content(file_hash, text_content)

        self._maybe_snapshot_version(file_id, file_hash, path, ext)

        events.publish("file-indexed", {"id": file_id, "path": str(path), "hash": file_hash})
        return file_id

    def _maybe_snapshot_version(self, file_id, file_hash, path, ext):
        from . import versions as versions_module
        tags = tagging.get_tags(file_hash)
        if ext in config.VERSIONED_EXTENSIONS or any(t["tag"] == "report" for t in tags):
            try:
                versions_module.snapshot(file_id, path)
            except Exception:
                pass

    def _restore_retained_tags(self, file_hash: str):
        with db.cursor() as cur:
            cur.execute("SELECT * FROM retained_tags WHERE file_hash=?", (file_hash,))
            rows = cur.fetchall()
            for row in rows:
                cur.execute(
                    """INSERT INTO tags (file_hash, tag, source, confidence, event_uid, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(file_hash, tag, source) DO NOTHING""",
                    (file_hash, row["tag"], row["source"], row["confidence"], row["event_uid"], time.time()),
                )
            cur.execute("DELETE FROM retained_tags WHERE file_hash=?", (file_hash,))

    def handle_removed(self, path: Path):
        path_str = str(path)
        with db.cursor() as cur:
            cur.execute("SELECT * FROM files WHERE path=? AND deleted=0", (path_str,))
            row = cur.fetchone()
            if not row:
                return
            file_hash = row["hash"]
            cur.execute("UPDATE files SET deleted=1, deleted_at=? WHERE id=?", (time.time(), row["id"]))
            cur.execute("SELECT tag, source, confidence, event_uid FROM tags WHERE file_hash=?", (file_hash,))
            tag_rows = cur.fetchall()
            for tag_row in tag_rows:
                cur.execute(
                    """INSERT INTO retained_tags (file_hash, tag, source, confidence, event_uid, deleted_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (file_hash, tag_row["tag"], tag_row["source"], tag_row["confidence"],
                     tag_row["event_uid"], time.time()),
                )
        events.publish("file-removed", {"path": path_str})

    def purge_expired_retained_tags(self):
        cutoff = time.time() - config.TAG_KEEP_DAYS_AFTER_DELETE * 86400
        with db.cursor() as cur:
            cur.execute("DELETE FROM retained_tags WHERE deleted_at < ?", (cutoff,))


class _Handler(FileSystemEventHandler):
    def __init__(self, indexer: Indexer):
        self.indexer = indexer

    def on_created(self, event):
        if not event.is_directory:
            self._debounced_index(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._debounced_index(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self.indexer.handle_removed(Path(event.src_path))
            self._debounced_index(Path(event.dest_path))

    def on_deleted(self, event):
        if not event.is_directory:
            self.indexer.handle_removed(Path(event.src_path))

    def _debounced_index(self, path: Path):
        if not _should_index(path):
            return

        def _run():
            time.sleep(0.5)
            try:
                self.indexer.index_file(path)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

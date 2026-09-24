"""Snapshots files tagged 'report' or with a versioned extension into a
hidden versions folder, deduplicated by content hash, keeping the last N."""
import shutil
import time
from pathlib import Path

from . import config, db
from .indexer import hash_file
from .textextract import extract_text


def should_version(file_row, tags) -> bool:
    ext = (file_row.get("ext") or "").lower()
    if ext in config.VERSIONED_EXTENSIONS:
        return True
    return any(t["tag"] == "report" for t in tags)


def snapshot(file_id: int, path: Path):
    """Snapshot the current content of files.id=file_id. Versions are keyed
    by that stable row id (survives renames/moves/edits), never by content
    hash — every new version has a different hash by definition, so keying
    on it would orphan every prior snapshot as soon as the file changes."""
    if not path.exists():
        return None
    content_hash = hash_file(path)

    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM versions WHERE file_id=? AND content_hash=? ORDER BY id DESC LIMIT 1",
            (file_id, content_hash),
        )
        if cur.fetchone():
            return None

    dest_dir = config.VERSIONS_DIR / str(file_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = dest_dir / f"{int(time.time())}_{content_hash[:12]}{path.suffix}"
    shutil.copy2(str(path), str(snapshot_path))

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO versions (file_id, content_hash, snapshot_path, created_at) VALUES (?, ?, ?, ?)",
            (file_id, content_hash, str(snapshot_path), time.time()),
        )
        cur.execute("SELECT id, snapshot_path FROM versions WHERE file_id=? ORDER BY id DESC", (file_id,))
        rows = cur.fetchall()
        for old in rows[config.MAX_VERSIONS_PER_FILE:]:
            Path(old["snapshot_path"]).unlink(missing_ok=True)
            cur.execute("DELETE FROM versions WHERE id=?", (old["id"],))

    return str(snapshot_path)


def list_versions(file_id: int):
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, content_hash, snapshot_path, created_at FROM versions WHERE file_id=? ORDER BY id DESC",
            (file_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def restore_version(version_id: int, target_path: Path):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM versions WHERE id=?", (version_id,))
        row = cur.fetchone()
        if not row:
            raise FileNotFoundError("version not found")
    shutil.copy2(row["snapshot_path"], str(target_path))
    return str(target_path)


def diff_version(version_id: int, current_path: Path):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM versions WHERE id=?", (version_id,))
        row = cur.fetchone()
        if not row:
            raise FileNotFoundError("version not found")
    old_text = extract_text(Path(row["snapshot_path"])).splitlines()
    new_text = extract_text(current_path).splitlines() if current_path.exists() else []
    import difflib
    return list(difflib.unified_diff(old_text, new_text, lineterm=""))

"""Real file operations (rename/move/copy/delete) plus an undo log.

All operations are refused if the source or destination path resolves
outside the configured watched folders.
"""
import json
import shutil
import time
from pathlib import Path

from . import db, events
from .pathsafety import assert_path_allowed

try:
    from send2trash import send2trash
    HAVE_SEND2TRASH = True
except ImportError:
    HAVE_SEND2TRASH = False


def _log_operation(op_type: str, payload: dict) -> int:
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO operations (op_type, payload, undone, created_at) VALUES (?, ?, 0, ?)",
            (op_type, json.dumps(payload), time.time()),
        )
        return cur.lastrowid


def _update_file_path(old_path: str, new_path: str):
    with db.cursor() as cur:
        cur.execute("UPDATE files SET path=?, name=? WHERE path=?", (new_path, Path(new_path).name, old_path))


def rename_file(file_id: int, new_name: str) -> dict:
    row = _get_file_row(file_id)
    old_path = Path(row["path"])
    new_path = old_path.with_name(new_name)
    assert_path_allowed(old_path)
    assert_path_allowed(new_path)

    old_path.rename(new_path)
    _update_file_path(str(old_path), str(new_path))
    op_id = _log_operation("rename", {"from": str(old_path), "to": str(new_path), "file_id": file_id})
    events.publish("file-renamed", {"id": file_id, "from": str(old_path), "to": str(new_path)})
    return {"op_id": op_id, "new_path": str(new_path)}


def move_files(file_ids, target_folder: str) -> dict:
    target = Path(target_folder)
    assert_path_allowed(target)
    target.mkdir(parents=True, exist_ok=True)

    moves = []
    for file_id in file_ids:
        row = _get_file_row(file_id)
        old_path = Path(row["path"])
        new_path = target / old_path.name
        assert_path_allowed(old_path)
        assert_path_allowed(new_path)
        shutil.move(str(old_path), str(new_path))
        _update_file_path(str(old_path), str(new_path))
        moves.append({"from": str(old_path), "to": str(new_path), "file_id": file_id})

    op_id = _log_operation("move", {"moves": moves})
    events.publish("files-moved", {"moves": moves})
    return {"op_id": op_id, "moves": moves}


def copy_files(file_ids, target_folder: str) -> dict:
    target = Path(target_folder)
    assert_path_allowed(target)
    target.mkdir(parents=True, exist_ok=True)

    copies = []
    for file_id in file_ids:
        row = _get_file_row(file_id)
        src_path = Path(row["path"])
        dst_path = target / src_path.name
        assert_path_allowed(src_path)
        assert_path_allowed(dst_path)
        shutil.copy2(str(src_path), str(dst_path))
        copies.append({"from": str(src_path), "to": str(dst_path)})

    op_id = _log_operation("copy", {"copies": copies})
    return {"op_id": op_id, "copies": copies}


def delete_files(file_ids, skip_confirmation=False) -> dict:
    deleted = []
    for file_id in file_ids:
        row = _get_file_row(file_id)
        path = Path(row["path"])
        assert_path_allowed(path)
        if HAVE_SEND2TRASH:
            send2trash(str(path))
        else:
            path.unlink(missing_ok=True)
        deleted.append({"file_id": file_id, "path": str(path)})

    op_id = _log_operation("delete", {"deleted": deleted, "skip_confirmation": skip_confirmation})
    events.publish("files-deleted", {"deleted": deleted})
    return {"op_id": op_id, "deleted": deleted}


def undo_last() -> dict:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM operations WHERE undone=0 ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {"undone": False, "reason": "nothing to undo"}
        payload = json.loads(row["payload"])
        op_type = row["op_type"]

        if op_type == "rename":
            new_path, old_path = Path(payload["to"]), Path(payload["from"])
            if new_path.exists():
                new_path.rename(old_path)
                _update_file_path(str(new_path), str(old_path))
        elif op_type == "move":
            for move in payload["moves"]:
                dst, src = Path(move["to"]), Path(move["from"])
                if dst.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
                    _update_file_path(str(dst), str(src))
        elif op_type == "copy":
            for copy in payload["copies"]:
                dst = Path(copy["to"])
                if dst.exists():
                    dst.unlink()
        elif op_type == "delete":
            return {"undone": False, "reason": "deleted files went to the recycle bin; restore from there"}

        cur.execute("UPDATE operations SET undone=1 WHERE id=?", (row["id"],))
        return {"undone": True, "op_type": op_type}


def _get_file_row(file_id: int):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
        if not row:
            raise FileNotFoundError(f"No file with id {file_id}")
        return row

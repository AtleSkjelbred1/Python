"""Physical, on-demand sorting: moves all files with a tag into a folder
structure such as Documents/Studies/<course>/<subtag>."""
from pathlib import Path

from . import config, db, fileops

DEFAULT_TEMPLATE = "Studies/{course}/{subtag}"


def _target_root():
    for folder in config.WATCHED_FOLDERS:
        if Path(folder).name.lower() == "documents":
            return Path(folder)
    return Path(config.WATCHED_FOLDERS[0])


def _plan(tag: str, template: str = DEFAULT_TEMPLATE):
    with db.cursor() as cur:
        cur.execute(
            "SELECT f.id, f.path, f.name FROM files f JOIN tags t ON f.hash = t.file_hash "
            "WHERE t.tag=? AND f.deleted=0",
            (tag,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    root = _target_root()
    moves = []
    for row in rows:
        dest_folder = root / template.format(course=tag, subtag="general")
        moves.append({
            "file_id": row["id"],
            "from": row["path"],
            "to": str(dest_folder / row["name"]),
        })
    return moves


def preview_archive(tag: str, template: str = DEFAULT_TEMPLATE):
    return _plan(tag, template)


def apply_archive(tag: str, template: str = DEFAULT_TEMPLATE):
    plan = _plan(tag, template)
    by_target = {}
    for move in plan:
        target_folder = str(Path(move["to"]).parent)
        by_target.setdefault(target_folder, []).append(move["file_id"])

    results = []
    for target_folder, file_ids in by_target.items():
        results.append(fileops.move_files(file_ids, target_folder))
    return results

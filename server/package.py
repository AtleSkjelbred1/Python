"""Builds a submission-ready zip for a calendar deadline: collects files
linked to the event, lets the caller pick which to include and how to
rename them, and writes the zip into Downloads."""
import zipfile
from pathlib import Path

from . import calendar as calendar_source
from . import config, db


def _downloads_folder():
    for folder in config.WATCHED_FOLDERS:
        if Path(folder).name.lower() == "downloads":
            return Path(folder)
    return Path(config.WATCHED_FOLDERS[0])


def files_for_event(event_uid: str):
    with db.cursor() as cur:
        cur.execute(
            "SELECT f.id, f.path, f.name, f.ext FROM files f JOIN tags t ON f.hash = t.file_hash "
            "WHERE t.event_uid=? AND f.deleted=0",
            (event_uid,),
        )
        return [dict(r) for r in cur.fetchall()]


def preview_package(event_uid: str):
    event = calendar_source.get_event_by_uid(event_uid)
    return {"event": calendar_source.event_to_json(event) if event else None,
            "files": files_for_event(event_uid)}


def build_package(event_uid: str, file_ids, pattern: str, student_name: str = "student"):
    event = calendar_source.get_event_by_uid(event_uid)
    course = (event["course"] if event else None) or "course"
    assignment = (event["title"] if event else "assignment").replace(" ", "_")

    with db.cursor() as cur:
        cur.execute(
            f"SELECT id, path, name, ext FROM files WHERE id IN "
            f"({','.join('?' for _ in file_ids)})",
            file_ids,
        )
        rows = [dict(r) for r in cur.fetchall()]

    downloads = _downloads_folder()
    downloads.mkdir(parents=True, exist_ok=True)
    zip_name = f"{course}_{assignment}_submission.zip"
    zip_path = downloads / zip_name

    with zipfile.ZipFile(zip_path, "w") as zf:
        for row in rows:
            ext = row["ext"].lstrip(".") if row["ext"] else ""
            new_name = pattern.format(course=course, assignment=assignment, name=student_name, ext=ext)
            zf.write(row["path"], arcname=new_name)

    return str(zip_path)

"""Storage overview: space used per course/tag/file type, and the largest files."""
from . import db


def overview():
    with db.cursor() as cur:
        cur.execute("SELECT id, hash, name, ext, size FROM files WHERE deleted=0")
        files = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT file_hash, tag FROM tags")
        tag_rows = [dict(r) for r in cur.fetchall()]

    tags_by_hash = {}
    for row in tag_rows:
        tags_by_hash.setdefault(row["file_hash"], []).append(row["tag"])

    by_tag = {}
    by_ext = {}
    for f in files:
        by_ext[f["ext"] or "(none)"] = by_ext.get(f["ext"] or "(none)", 0) + (f["size"] or 0)
        for tag in tags_by_hash.get(f["hash"], []):
            by_tag[tag] = by_tag.get(tag, 0) + (f["size"] or 0)

    largest = sorted(files, key=lambda f: f["size"] or 0, reverse=True)[:50]

    return {
        "by_tag": by_tag,
        "by_extension": by_ext,
        "largest_files": largest,
        "total_bytes": sum(f["size"] or 0 for f in files),
    }

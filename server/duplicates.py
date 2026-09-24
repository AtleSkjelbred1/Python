"""Exact duplicate detection by hash and near-duplicate text detection."""
import difflib
import re
from pathlib import Path

from . import config, db
from .textextract import extract_text

_COPY_MARKERS = re.compile(r"\s*[-_ ]*\(\d+\)$|\s*[-_]+\s*copy$|\s*[-_]+\s*kopi$", re.IGNORECASE)


def _clean_name_score(name: str) -> int:
    """Lower is 'cleaner' (no copy markers)."""
    stem = Path(name).stem
    return 1 if _COPY_MARKERS.search(stem) else 0


def suggest_keeper(file_rows):
    """Given rows with name/ctime, pick the keeper: cleanest name, then oldest."""
    return sorted(file_rows, key=lambda r: (_clean_name_score(r["name"]), r["ctime"] or 0))[0]


def find_exact_duplicates():
    with db.cursor() as cur:
        cur.execute("SELECT id, hash, path, name, ctime, size FROM files WHERE deleted=0")
        rows = [dict(r) for r in cur.fetchall()]

    by_hash = {}
    for row in rows:
        by_hash.setdefault(row["hash"], []).append(row)

    groups = []
    for file_hash, group in by_hash.items():
        if len(group) < 2:
            continue
        keeper = suggest_keeper(group)
        groups.append({
            "hash": file_hash,
            "files": group,
            "suggested_keeper_id": keeper["id"],
            "wasted_bytes": (group[0]["size"] or 0) * (len(group) - 1),
        })
    return groups


def _shingles(text: str, size=2):
    words = text.split()
    return {" ".join(words[i:i + size]) for i in range(max(len(words) - size + 1, 1))}


def similarity(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    shingles_a, shingles_b = _shingles(text_a), _shingles(text_b)
    if shingles_a and shingles_b:
        intersection = len(shingles_a & shingles_b)
        union = len(shingles_a | shingles_b)
        jaccard = intersection / union if union else 0.0
    else:
        jaccard = 0.0
    ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
    # Average both signals: difflib's character-level ratio alone spikes on
    # shared boilerplate/templates (e.g. two lecture-notes files with the
    # same skeleton but different topics), which would otherwise flag
    # structurally similar but substantively different documents as
    # near-duplicates. Word-shingle jaccard alone is too brittle on short
    # text (a single punctuation change can shift every shingle).
    return (jaccard + ratio) / 2


def find_near_duplicates(threshold=None):
    threshold = threshold or config.NEAR_DUP_THRESHOLD
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, hash, path, name, ext FROM files WHERE deleted=0 AND ext IN "
            "('.txt','.md','.tex','.docx','.pdf','.pptx')"
        )
        rows = [dict(r) for r in cur.fetchall()]

    texts = {}
    for row in rows:
        texts[row["id"]] = extract_text(Path(row["path"]))

    pairs = []
    seen_hashes = set()
    for i, a in enumerate(rows):
        if not texts[a["id"]]:
            continue
        for b in rows[i + 1:]:
            if a["hash"] == b["hash"]:
                continue
            pair_key = tuple(sorted((a["hash"], b["hash"])))
            if pair_key in seen_hashes:
                continue
            if not texts[b["id"]]:
                continue
            score = similarity(texts[a["id"]], texts[b["id"]])
            if score > threshold:
                seen_hashes.add(pair_key)
                pairs.append({
                    "a": {"id": a["id"], "path": a["path"], "name": a["name"]},
                    "b": {"id": b["id"], "path": b["path"], "name": b["name"]},
                    "similarity": round(score, 3),
                })
    return pairs


def diff_files(id_a: int, id_b: int):
    with db.cursor() as cur:
        cur.execute("SELECT id, path FROM files WHERE id IN (?, ?)", (id_a, id_b))
        rows = {r["id"]: r["path"] for r in cur.fetchall()}
    if id_a not in rows or id_b not in rows:
        return None
    text_a = extract_text(Path(rows[id_a])).splitlines()
    text_b = extract_text(Path(rows[id_b])).splitlines()
    diff = list(difflib.unified_diff(text_a, text_b, lineterm=""))
    return {"diff": diff}


def merge_tags_into_keeper(keeper_hash: str, other_hashes):
    with db.cursor() as cur:
        for other_hash in other_hashes:
            cur.execute("SELECT tag, source, confidence, event_uid FROM tags WHERE file_hash=?", (other_hash,))
            for row in cur.fetchall():
                cur.execute(
                    """INSERT INTO tags (file_hash, tag, source, confidence, event_uid, created_at)
                       VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                       ON CONFLICT(file_hash, tag, source) DO UPDATE SET
                         confidence=MAX(tags.confidence, excluded.confidence)""",
                    (keeper_hash, row["tag"], row["source"], row["confidence"], row["event_uid"]),
                )

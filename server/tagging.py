"""Tag assignment from multiple sources: rule, calendar, content, manual.

Higher-confidence manual tags are never overwritten by automatic sources.
"""
import re
import time
from datetime import datetime, timezone

from . import calendar as calendar_source
from . import config, db

EXT_TAGS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".tex": "tex",
    ".txt": "text",
    ".md": "markdown",
}


def _course_codes_in(text: str):
    return set(re.findall(config.COURSE_CODE_PATTERN, text.upper()))


def upsert_tag(file_hash: str, tag: str, source: str, confidence: float, event_uid: str = None):
    with db.cursor() as cur:
        cur.execute(
            "SELECT source, confidence FROM tags WHERE file_hash=? AND tag=?",
            (file_hash, tag),
        )
        existing = cur.fetchall()
        for row in existing:
            if row["source"] == "manual" and source != "manual":
                return False
        cur.execute(
            """INSERT INTO tags (file_hash, tag, source, confidence, event_uid, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(file_hash, tag, source) DO UPDATE SET
                 confidence=MAX(tags.confidence, excluded.confidence),
                 event_uid=COALESCE(excluded.event_uid, tags.event_uid)""",
            (file_hash, tag, source, confidence, event_uid, time.time()),
        )
    return True


def remove_tag(file_hash: str, tag: str, source: str = None):
    with db.cursor() as cur:
        if source:
            cur.execute("DELETE FROM tags WHERE file_hash=? AND tag=? AND source=?", (file_hash, tag, source))
        else:
            cur.execute("DELETE FROM tags WHERE file_hash=? AND tag=?", (file_hash, tag))


def get_tags(file_hash: str):
    with db.cursor() as cur:
        cur.execute(
            "SELECT tag, source, confidence, event_uid FROM tags WHERE file_hash=? ORDER BY confidence DESC",
            (file_hash,),
        )
        return [dict(row) for row in cur.fetchall()]


def set_manual_tag(file_hash: str, tag: str):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO tags (file_hash, tag, source, confidence, event_uid, created_at)
               VALUES (?, ?, 'manual', 1.0, NULL, ?)
               ON CONFLICT(file_hash, tag, source) DO UPDATE SET confidence=1.0""",
            (file_hash, tag, time.time()),
        )


def tag_from_rules(name: str, ext: str, text_content: str, file_hash: str):
    """Rule source: course code in filename/content, and file type."""
    for code in _course_codes_in(name):
        upsert_tag(file_hash, code, "rule", 0.9)
    if text_content:
        for code in _course_codes_in(text_content[:5000]):
            upsert_tag(file_hash, code, "rule", 0.6)
    ext_tag = EXT_TAGS.get(ext.lower())
    if ext_tag:
        upsert_tag(file_hash, ext_tag, "rule", 1.0)


def tag_from_calendar(file_hash: str, created_time: float):
    ts = datetime.fromtimestamp(created_time, tz=timezone.utc)
    event = calendar_source.find_event_near(ts)
    if event and event.get("course"):
        upsert_tag(file_hash, event["course"], "calendar", 0.8, event_uid=event["uid"])
        return event
    return None


def tag_from_content(file_hash: str, text_content: str):
    if not text_content:
        return
    lowered = text_content.lower()
    events = calendar_source.get_events()
    seen_courses = set()
    for event in events:
        course = event.get("course")
        if course and course not in seen_courses and course.lower() in lowered:
            upsert_tag(file_hash, course, "content", 0.5)
            seen_courses.add(course)
        title_words = [w for w in re.findall(r"[a-zA-Z]{4,}", event["title"]) if w.lower() in lowered]
        if title_words and course:
            upsert_tag(file_hash, course, "content", 0.55)

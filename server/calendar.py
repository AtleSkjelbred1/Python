"""Fetches and parses CANVAS_ICS / ICLOUD_ICS calendar feeds, with a 10 minute
cache and lightweight event classification."""
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar

from . import config

_cache = {"events": None, "fetched_at": 0.0}

DEADLINE_KEYWORDS = ("deadline", "due", "innlevering", "frist", "submission")
LAB_KEYWORDS = ("lab", "laboratory", "øving", "ovingslab", "workshop")
LECTURE_KEYWORDS = ("lecture", "forelesning", "class")


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url


def _classify(title: str) -> str:
    t = title.lower()
    if any(k in t for k in DEADLINE_KEYWORDS):
        return "deadline"
    if any(k in t for k in LAB_KEYWORDS):
        return "lab"
    if any(k in t for k in LECTURE_KEYWORDS):
        return "lecture"
    return "other"


def extract_course_code(title: str):
    match = re.search(config.COURSE_CODE_PATTERN, title.upper())
    return match.group(0) if match else None


def _to_datetime(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    # date-only (all-day event)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _parse_feed(url: str, source: str):
    events = []
    url = _normalize_url(url)
    if not url:
        return events
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return events

    try:
        cal = Calendar.from_ical(resp.content)
    except ValueError:
        return events

    for component in cal.walk("VEVENT"):
        summary = str(component.get("summary", ""))
        dtstart = component.get("dtstart")
        if dtstart is None:
            continue
        start = _to_datetime(dtstart.dt)
        dtend = component.get("dtend")
        end = _to_datetime(dtend.dt) if dtend else start
        uid = str(component.get("uid", f"{source}-{summary}-{start.isoformat()}"))
        events.append({
            "uid": uid,
            "title": summary,
            "start": start,
            "end": end,
            "course": extract_course_code(summary),
            "kind": _classify(summary),
            "source": source,
        })
    return events


def get_events(force=False):
    now = time.time()
    if not force and _cache["events"] is not None and now - _cache["fetched_at"] < config.CALENDAR_CACHE_SECONDS:
        return _cache["events"]

    events = []
    events.extend(_parse_feed(config.CANVAS_ICS, "canvas"))
    events.extend(_parse_feed(config.ICLOUD_ICS, "icloud"))
    events.sort(key=lambda e: e["start"])

    _cache["events"] = events
    _cache["fetched_at"] = now
    return events


def get_week_events(reference=None):
    reference = reference or datetime.now(timezone.utc)
    start_of_week = reference - timedelta(days=reference.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7)
    return [e for e in get_events() if start_of_week <= e["start"] < end_of_week]


def get_todays_events(reference=None):
    reference = reference or datetime.now(timezone.utc)
    day_start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return [e for e in get_events() if day_start <= e["start"] < day_end]


def find_event_near(timestamp: datetime, window_minutes=None):
    """Return an event whose window (start-window, end+window) contains timestamp."""
    window = timedelta(minutes=window_minutes or config.CALENDAR_LINK_WINDOW_MINUTES)
    for event in get_events():
        if event["start"] - window <= timestamp <= event["end"] + window:
            return event
    return None


def get_event_by_uid(uid: str):
    for event in get_events():
        if event["uid"] == uid:
            return event
    return None


def event_to_json(event: dict) -> dict:
    return {
        "uid": event["uid"],
        "title": event["title"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat(),
        "course": event["course"],
        "kind": event["kind"],
        "source": event["source"],
    }

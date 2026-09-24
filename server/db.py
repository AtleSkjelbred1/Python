"""SQLite access layer. All tables keyed on file hash where possible so tags
survive move/rename."""
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    ext TEXT,
    size INTEGER,
    ctime REAL,
    mtime REAL,
    deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at REAL
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    tag TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL,
    event_uid TEXT,
    created_at REAL,
    UNIQUE(file_hash, tag, source)
);
CREATE INDEX IF NOT EXISTS idx_tags_hash ON tags(file_hash);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    query TEXT
);

CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    undone INTEGER NOT NULL DEFAULT 0,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    folder TEXT,
    pattern TEXT,
    age_days INTEGER,
    action TEXT NOT NULL,
    target TEXT,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cleanup_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at REAL,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_versions_file_id ON versions(file_id);

CREATE TABLE IF NOT EXISTS retained_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    tag TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL,
    event_uid TEXT,
    deleted_at REAL NOT NULL
);
"""


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # WAL lets readers (API requests) proceed while the indexer thread is
        # writing, instead of blocking behind its transactions.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        _local.conn = conn
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

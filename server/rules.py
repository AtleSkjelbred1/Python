"""User-defined cleanup rules. Rules only ever produce suggestions; nothing
is deleted or moved until the user approves it in the Cleanup tab."""
import fnmatch
import time
from pathlib import Path

from . import db


def list_rules():
    with db.cursor() as cur:
        cur.execute("SELECT * FROM rules ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def create_rule(name, folder, pattern, age_days, action, target=None, enabled=True):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO rules (name, folder, pattern, age_days, action, target, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, folder, pattern, age_days, action, target, 1 if enabled else 0),
        )
        return cur.lastrowid


def delete_rule(rule_id):
    with db.cursor() as cur:
        cur.execute("DELETE FROM rules WHERE id=?", (rule_id,))
        cur.execute("DELETE FROM cleanup_suggestions WHERE rule_id=?", (rule_id,))


def _matches(rule, file_row):
    path = Path(file_row["path"])
    if rule["folder"] and rule["folder"] not in str(path.parent):
        return False
    if rule["pattern"] and not fnmatch.fnmatch(path.name.lower(), rule["pattern"].lower()):
        return False
    if rule["age_days"]:
        age_seconds = time.time() - (file_row["mtime"] or 0)
        if age_seconds < rule["age_days"] * 86400:
            return False
    return True


def evaluate_rules():
    """Re-evaluates all enabled rules against indexed files and refreshes
    the cleanup_suggestions table."""
    with db.cursor() as cur:
        cur.execute("SELECT * FROM files WHERE deleted=0")
        files = [dict(r) for r in cur.fetchall()]
        cur.execute("DELETE FROM cleanup_suggestions WHERE resolved=0")

        for rule in list_rules():
            if not rule["enabled"]:
                continue
            for file_row in files:
                if _matches(rule, file_row):
                    cur.execute(
                        """INSERT INTO cleanup_suggestions (rule_id, file_hash, path, action, created_at, resolved)
                           VALUES (?, ?, ?, ?, ?, 0)""",
                        (rule["id"], file_row["hash"], file_row["path"], rule["action"], time.time()),
                    )
    return list_suggestions()


def list_suggestions():
    with db.cursor() as cur:
        cur.execute("SELECT * FROM cleanup_suggestions WHERE resolved=0 ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def resolve_suggestions(ids):
    with db.cursor() as cur:
        cur.executemany("UPDATE cleanup_suggestions SET resolved=1 WHERE id=?", [(i,) for i in ids])

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Rebuilds server.config/server.db against an isolated temp DB and a
    temp set of watched folders, then reloads the modules under test so
    they pick up the new configuration."""
    watched_a = tmp_path / "Downloads"
    watched_b = tmp_path / "Documents"
    watched_a.mkdir()
    watched_b.mkdir()

    monkeypatch.setenv("WATCHED_FOLDERS", f"{watched_a},{watched_b}")
    monkeypatch.setenv("FILESORTER_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("CANVAS_ICS", "")
    monkeypatch.setenv("ICLOUD_ICS", "")

    import server.config as config
    importlib.reload(config)
    import server.db as db
    importlib.reload(db)
    db.init_db()
    import server.pathsafety as pathsafety
    importlib.reload(pathsafety)
    import server.tagging as tagging
    importlib.reload(tagging)
    import server.duplicates as duplicates
    importlib.reload(duplicates)
    import server.rules as rules
    importlib.reload(rules)
    import server.fileops as fileops
    importlib.reload(fileops)

    return {
        "config": config,
        "db": db,
        "pathsafety": pathsafety,
        "tagging": tagging,
        "duplicates": duplicates,
        "rules": rules,
        "fileops": fileops,
        "watched_a": watched_a,
        "watched_b": watched_b,
        "tmp_path": tmp_path,
    }

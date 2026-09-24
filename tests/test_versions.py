from pathlib import Path


def _insert_file(db, path, ext):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("initial-hash", str(path), path.name, ext, path.stat().st_size, 0, 0),
        )
        cur.execute("SELECT id FROM files WHERE path=?", (str(path),))
        return cur.fetchone()["id"]


def test_version_history_survives_content_change(env):
    import server.versions as versions
    db = env["db"]

    report = env["watched_a"] / "report.tex"
    report.write_text("v1 content")
    file_id = _insert_file(db, report, ".tex")

    versions.snapshot(file_id, report)
    assert len(versions.list_versions(file_id)) == 1

    # Editing the file changes its content hash. Version history must still
    # be reachable by the file's stable id, not by (now stale) content hash.
    report.write_text("v2 content, substantially different")
    versions.snapshot(file_id, report)

    history = versions.list_versions(file_id)
    assert len(history) == 2, "prior version was orphaned after a content change"


def test_snapshot_skips_duplicate_identical_content(env):
    import server.versions as versions
    db = env["db"]

    report = env["watched_a"] / "report2.tex"
    report.write_text("same content")
    file_id = _insert_file(db, report, ".tex")

    versions.snapshot(file_id, report)
    versions.snapshot(file_id, report)  # identical content again

    assert len(versions.list_versions(file_id)) == 1


def test_restore_version_writes_old_content_back(env):
    import server.versions as versions
    db = env["db"]

    report = env["watched_a"] / "report3.tex"
    report.write_text("original")
    file_id = _insert_file(db, report, ".tex")
    versions.snapshot(file_id, report)
    original_version_id = versions.list_versions(file_id)[0]["id"]

    report.write_text("changed")
    versions.snapshot(file_id, report)
    assert report.read_text() == "changed"

    versions.restore_version(original_version_id, report)
    assert report.read_text() == "original"

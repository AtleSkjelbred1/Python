import time


def _touch(path, age_days=0):
    path.write_text("x")
    old_time = time.time() - age_days * 86400
    import os
    os.utime(path, (old_time, old_time))


def test_rule_matches_pattern_and_age(env):
    rules = env["rules"]
    db = env["db"]

    old_exe = env["watched_a"] / "installer.exe"
    _touch(old_exe, age_days=20)
    new_exe = env["watched_a"] / "fresh.exe"
    _touch(new_exe, age_days=1)

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h1", str(old_exe), old_exe.name, ".exe", 10, old_exe.stat().st_mtime, old_exe.stat().st_mtime),
        )
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h2", str(new_exe), new_exe.name, ".exe", 10, new_exe.stat().st_mtime, new_exe.stat().st_mtime),
        )

    rules.create_rule(
        name="old installers",
        folder=str(env["watched_a"]),
        pattern="*.exe",
        age_days=14,
        action="delete",
    )

    suggestions = rules.evaluate_rules()
    matched_paths = {s["path"] for s in suggestions}
    assert str(old_exe) in matched_paths
    assert str(new_exe) not in matched_paths


def test_disabled_rule_produces_no_suggestions(env):
    rules = env["rules"]
    db = env["db"]

    target = env["watched_a"] / "old.png"
    _touch(target, age_days=40)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h3", str(target), target.name, ".png", 10, target.stat().st_mtime, target.stat().st_mtime),
        )
    rules.create_rule(
        name="old screenshots", folder=str(env["watched_a"]), pattern="*.png",
        age_days=30, action="archive", enabled=False,
    )
    suggestions = rules.evaluate_rules()
    assert suggestions == []


def test_resolve_suggestions_marks_resolved(env):
    rules = env["rules"]
    db = env["db"]
    target = env["watched_a"] / "old.png"
    _touch(target, age_days=40)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("h4", str(target), target.name, ".png", 10, target.stat().st_mtime, target.stat().st_mtime),
        )
    rules.create_rule(
        name="old screenshots", folder=str(env["watched_a"]), pattern="*.png",
        age_days=30, action="archive",
    )
    suggestions = rules.evaluate_rules()
    assert len(suggestions) == 1
    rules.resolve_suggestions([s["id"] for s in suggestions])
    assert rules.list_suggestions() == []

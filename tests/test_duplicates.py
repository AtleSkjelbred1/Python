def test_suggest_keeper_prefers_name_without_copy_marker(env):
    duplicates = env["duplicates"]
    rows = [
        {"name": "report (1).pdf", "ctime": 100, "id": 1},
        {"name": "report.pdf", "ctime": 200, "id": 2},
    ]
    keeper = duplicates.suggest_keeper(rows)
    assert keeper["id"] == 2


def test_suggest_keeper_prefers_oldest_when_names_equally_clean(env):
    duplicates = env["duplicates"]
    rows = [
        {"name": "report.pdf", "ctime": 200, "id": 1},
        {"name": "report.pdf", "ctime": 50, "id": 2},
    ]
    keeper = duplicates.suggest_keeper(rows)
    assert keeper["id"] == 2


def test_find_exact_duplicates_groups_by_hash(env):
    db = env["db"]
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO files (hash, path, name, ext, size, ctime, mtime) VALUES "
            "('h1', '/a/report.pdf', 'report.pdf', '.pdf', 100, 200, 200), "
            "('h1', '/a/report (1).pdf', 'report (1).pdf', '.pdf', 100, 300, 300), "
            "('h2', '/a/other.pdf', 'other.pdf', '.pdf', 50, 100, 100)"
        )
    groups = env["duplicates"].find_exact_duplicates()
    assert len(groups) == 1
    assert groups[0]["hash"] == "h1"
    assert len(groups[0]["files"]) == 2


def test_similarity_identical_text_is_one(env):
    duplicates = env["duplicates"]
    text = "This report covers the measurement lab results in detail."
    assert duplicates.similarity(text, text) == 1.0


def test_similarity_unrelated_text_is_low(env):
    duplicates = env["duplicates"]
    score = duplicates.similarity(
        "Completely unrelated content about cooking recipes and food.",
        "A totally different topic regarding space exploration missions.",
    )
    assert score < 0.5


def test_similarity_near_duplicate_text_exceeds_threshold(env):
    duplicates = env["duplicates"]
    a = "Introduction. The experiment measured voltage across the resistor network."
    b = "Introduction. The experiment measured voltage across the resistor network!"
    assert duplicates.similarity(a, b) > 0.85

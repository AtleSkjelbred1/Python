def test_rule_tag_extracts_course_code_from_filename(env):
    tagging = env["tagging"]
    tagging.tag_from_rules("ING2508_lab_report.pdf", ".pdf", "", "hash1")
    tags = {t["tag"] for t in tagging.get_tags("hash1")}
    assert "ING2508" in tags
    assert "pdf" in tags


def test_rule_tag_from_content_lower_confidence_than_filename(env):
    tagging = env["tagging"]
    tagging.tag_from_rules("notes.txt", ".txt", "this is about ING1507 basics", "hash2")
    tags = {t["tag"]: t["confidence"] for t in tagging.get_tags("hash2") if t["source"] == "rule"}
    assert tags["ING1507"] < 0.9


def test_manual_tag_is_never_overwritten_by_automatic_source(env):
    tagging = env["tagging"]
    tagging.set_manual_tag("hash3", "ING2508")
    changed = tagging.upsert_tag("hash3", "ING2508", "rule", 0.9)
    assert changed is False
    tags = tagging.get_tags("hash3")
    manual = [t for t in tags if t["tag"] == "ING2508" and t["source"] == "manual"]
    assert manual and manual[0]["confidence"] == 1.0


def test_remove_tag_removes_only_given_source(env):
    tagging = env["tagging"]
    tagging.upsert_tag("hash4", "ING2508", "rule", 0.9)
    tagging.upsert_tag("hash4", "ING2508", "content", 0.5)
    tagging.remove_tag("hash4", "ING2508", source="rule")
    remaining = tagging.get_tags("hash4")
    assert len(remaining) == 1
    assert remaining[0]["source"] == "content"


def test_content_tag_matches_calendar_course_mentioned_in_text(env, monkeypatch):
    tagging = env["tagging"]

    fake_event = {
        "uid": "u1", "title": "ING2508 Lab session", "course": "ING2508",
        "kind": "lab", "source": "canvas",
    }
    monkeypatch.setattr("server.calendar.get_events", lambda: [fake_event])

    tagging.tag_from_content("hash5", "Remember to bring your ING2508 lab notebook")
    tags = {t["tag"] for t in tagging.get_tags("hash5")}
    assert "ING2508" in tags

import os


def test_allows_path_inside_watched_folder(env):
    allowed_file = env["watched_a"] / "note.txt"
    allowed_file.write_text("hi")
    assert env["pathsafety"].is_path_allowed(allowed_file)


def test_rejects_path_outside_watched_folders(env):
    outside = env["tmp_path"].parent / "outside.txt"
    assert not env["pathsafety"].is_path_allowed(outside)


def test_rejects_dotdot_traversal_out_of_watched_folder(env):
    traversal = env["watched_a"] / ".." / ".." / "etc" / "passwd"
    assert not env["pathsafety"].is_path_allowed(traversal)


def test_rejects_symlink_escaping_watched_folder(env):
    real_secret = env["tmp_path"] / "secret.txt"
    real_secret.write_text("secret")
    link = env["watched_a"] / "link.txt"
    try:
        os.symlink(real_secret, link)
    except (OSError, NotImplementedError):
        return
    assert not env["pathsafety"].is_path_allowed(link)


def test_assert_path_allowed_raises_for_disallowed_path(env):
    outside = env["tmp_path"].parent / "outside.txt"
    try:
        env["pathsafety"].assert_path_allowed(outside)
        assert False, "expected PermissionError"
    except PermissionError:
        pass

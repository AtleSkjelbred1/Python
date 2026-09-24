"""Guards against file operations that would touch anything outside the
configured watched folders. Resolves symlinks and '..' before comparing."""
import os
from pathlib import Path

from . import config


def _resolved_watched_roots():
    return [Path(os.path.realpath(f)) for f in config.WATCHED_FOLDERS]


def is_path_allowed(path) -> bool:
    try:
        resolved = Path(os.path.realpath(str(path)))
    except (OSError, ValueError):
        return False
    for root in _resolved_watched_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def assert_path_allowed(path):
    if not is_path_allowed(path):
        raise PermissionError(f"Path outside watched folders is not allowed: {path}")

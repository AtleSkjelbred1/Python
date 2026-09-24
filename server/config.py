"""Central configuration, loaded from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

IS_WINDOWS = os.name == "nt"


def _default_watched_folders():
    home = Path.home()
    return [str(home / "Downloads"), str(home / "Documents")]


def _split_folders(raw: str):
    return [p.strip() for p in raw.split(",") if p.strip()]


CANVAS_ICS = os.environ.get("CANVAS_ICS", "")
ICLOUD_ICS = os.environ.get("ICLOUD_ICS", "")

_watched_raw = os.environ.get("WATCHED_FOLDERS", "")
WATCHED_FOLDERS = _split_folders(_watched_raw) if _watched_raw else _default_watched_folders()
WATCHED_FOLDERS = [str(Path(p).expanduser()) for p in WATCHED_FOLDERS]

HOST = os.environ.get("FILESORTER_HOST", "127.0.0.1")
PORT = int(os.environ.get("FILESORTER_PORT", "5000"))

HOTKEY = os.environ.get("FILESORTER_HOTKEY", "win+shift+f")
BROWSER = os.environ.get("FILESORTER_BROWSER", "msedge")

_db_env = os.environ.get("FILESORTER_DB", "")
DATA_DIR = BASE_DIR / "server" / "data"
DB_PATH = Path(_db_env) if _db_env else DATA_DIR / "filesorter.db"

VERSIONS_DIR = DATA_DIR / "versions"
CALENDAR_CACHE_SECONDS = 600
NEAR_DUP_THRESHOLD = 0.85
CALENDAR_LINK_WINDOW_MINUTES = 30
COURSE_CODE_PATTERN = r"[A-Z]{2,4}\d{3,4}"

TEXT_EXTENSIONS = {".txt", ".md", ".tex"}
SUPPORTED_EXTRACT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".tex", ".txt", ".md"}
VERSIONED_TAGS = {"report"}
VERSIONED_EXTENSIONS = {".tex", ".docx"}
MAX_VERSIONS_PER_FILE = 30
TAG_KEEP_DAYS_AFTER_DELETE = 30

DATA_DIR.mkdir(parents=True, exist_ok=True)
VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

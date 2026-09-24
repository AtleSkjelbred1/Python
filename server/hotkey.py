"""Registers a global hotkey (Windows only) that opens filesorter.html as an
app window, reusing the window if one is already open."""
import subprocess
import threading

from . import config

IS_WINDOWS = config.IS_WINDOWS
_window_open = False


def _open_dashboard():
    global _window_open
    html_path = (config.BASE_DIR / "web" / "filesorter.html").resolve()
    url = f"file:///{html_path}#focus-search"
    subprocess.Popen([config.BROWSER, f"--app={url}"])
    _window_open = True


def register_hotkey():
    if not IS_WINDOWS:
        return False
    try:
        import keyboard
    except ImportError:
        return False

    def _thread():
        keyboard.add_hotkey(config.HOTKEY, _open_dashboard)
        keyboard.wait()

    threading.Thread(target=_thread, daemon=True).start()
    return True

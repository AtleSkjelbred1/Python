"""Windows Explorer control via pywin32's Shell.Application COM object.

Every function degrades gracefully (returns empty/False) on non-Windows
platforms so the rest of the app and the test suite work on Linux/macOS.
"""
import os
import tempfile
from pathlib import Path

from . import config, db

IS_WINDOWS = config.IS_WINDOWS


def _shell():
    import win32com.client
    return win32com.client.Dispatch("Shell.Application")


def list_windows():
    if not IS_WINDOWS:
        return []
    shell = _shell()
    windows = []
    for window in shell.Windows():
        try:
            path = window.Document.Folder.Self.Path
        except Exception:
            continue
        windows.append({"hwnd": window.HWND, "folder": path})
    return windows


def navigate(hwnd: int, folder: str):
    if not IS_WINDOWS:
        return False
    shell = _shell()
    for window in shell.Windows():
        if window.HWND == hwnd:
            window.Navigate(folder)
            return True
    return False


def close_window(hwnd: int):
    if not IS_WINDOWS:
        return False
    shell = _shell()
    for window in shell.Windows():
        if window.HWND == hwnd:
            window.Quit()
            return True
    return False


def open_folder(folder: str, select_paths=None):
    select_paths = select_paths or []
    if not IS_WINDOWS:
        return False
    import subprocess
    if select_paths:
        args = ["explorer", f"/select,{select_paths[0]}"]
        subprocess.Popen(args)
    else:
        os.startfile(folder)
    return True


def select_in_window(hwnd: int, paths):
    if not IS_WINDOWS:
        return False
    shell = _shell()
    for window in shell.Windows():
        if window.HWND == hwnd:
            folder_view = window.Document
            for path in paths:
                item = shell.NameSpace(str(Path(path).parent)).ParseName(Path(path).name)
                if item:
                    folder_view.SelectItem(item, 1 | 4)
            return True
    return False


def get_active_window_folder():
    if not IS_WINDOWS:
        return None
    import win32gui
    hwnd = win32gui.GetForegroundWindow()
    shell = _shell()
    for window in shell.Windows():
        if window.HWND == hwnd:
            try:
                return window.Document.Folder.Self.Path
            except Exception:
                return None
    return None


def build_tag_shortcut_folder(tag: str, file_paths):
    """Builds/rebuilds a folder of .lnk shortcuts for a tag in %TEMP%."""
    base = Path(tempfile.gettempdir()) / "filesorter" / tag
    base.mkdir(parents=True, exist_ok=True)
    for existing in base.glob("*.lnk"):
        existing.unlink()

    if not IS_WINDOWS:
        for path in file_paths:
            (base / (Path(path).name + ".lnk")).write_text(path)
        return str(base)

    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    for path in file_paths:
        shortcut_path = base / (Path(path).stem + ".lnk")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = str(path)
        shortcut.WorkingDirectory = str(Path(path).parent)
        shortcut.save()
    return str(base)


def open_tag_view(tag: str):
    with db.cursor() as cur:
        cur.execute(
            "SELECT f.path FROM files f JOIN tags t ON f.hash = t.file_hash WHERE t.tag=? AND f.deleted=0",
            (tag,),
        )
        paths = [row["path"] for row in cur.fetchall()]
    folder = build_tag_shortcut_folder(tag, paths)
    open_folder(folder)
    return folder

# Python.

# Nettside:https://atleskjelbred1.github.io/Python/

## Rift Clash (browser game)

A 3D platform fighter in a single HTML file: six original characters, three
stages, local 2-player or vs. a bot. Controls are listed in the in-game pause
menu.

- Play: https://atleskjelbred1.github.io/Python/web/smash-fighter.html
- Source: [`web/smash-fighter.html`](web/smash-fighter.html) — or just open the
  file in a browser (it loads Three.js from cdnjs, so it needs internet).
- Characters, animations and stage props: [KayKit](https://kaylousberg.com) by
  Kay Lousberg (CC0), embedded in the HTML file.

## File Sorter (local Windows app)

A local, offline-first file organizer with a Flask backend and a single-file
HTML/JS dashboard. It watches your Downloads/Documents folders, tags files
automatically (rules, calendar, content, or manual), finds duplicates,
lets you control File Explorer, and can build zip submissions for
deadlines pulled from your Canvas/iCloud calendars. Files are never moved or
deleted automatically — every destructive action needs your confirmation
(or an explicit rule you approved).

### Setup

1. Install Python 3.10+ and create a virtual environment:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your own values:
   ```powershell
   copy .env.example .env
   ```
   - `CANVAS_ICS` / `ICLOUD_ICS`: your personal calendar feed URLs (find
     yours in Canvas under Calendar → Calendar Feed, and in iCloud under
     Calendar → Share Calendar → Public Calendar). These are secret,
     unguessable links — keep them out of git, chat logs, and screenshots.
   - `WATCHED_FOLDERS`: comma-separated absolute paths to index. Defaults
     to your Downloads and Documents folders.
   - `FILESORTER_HOTKEY`: the global hotkey that opens the dashboard
     (Windows only), default `win+shift+f`.
3. `.env` is already in `.gitignore` — never commit it.

### Running

```powershell
python -m server.app
```

This starts the single local Flask server (default `http://localhost:5000`)
that serves both the file-sorting API and the `/week.json` / `/today/files`
calendar endpoints used by the dashboard, so only one background process is
needed. It also serves the dashboard itself at `/` — open
**`http://localhost:5000/`** in a browser (or let the global hotkey open it
as an app window) to use it. This is the recommended way to open it: it
keeps everything same-origin, so browser reloads and reconnects behave
correctly.

`web/filesorter.html` can still be opened directly as a `file://` page
(e.g. to preview the UI with no server running) — it falls back to sample
data if it can't reach `http://localhost:5000`. Reloading a `file://` page
can occasionally misbehave in Chromium-based browsers, though, so prefer
`http://localhost:5000/` for day-to-day use.

### Autostart on Windows (Task Scheduler)

1. Open Task Scheduler → **Create Task…**
2. **General**: name it "File Sorter", check "Run whether user is logged on
   or not", and "Run with highest privileges" if you need Explorer control.
3. **Triggers**: New… → "At log on".
4. **Actions**: New… → Action "Start a program":
   - Program/script: `<path to .venv>\Scripts\pythonw.exe`
   - Arguments: `-m server.app`
   - Start in: the repository root (the folder containing this README).
5. **Conditions**: uncheck "Start the task only if the computer is on AC
   power" if you want it to run on battery.
6. Save. The server will now start automatically at login and the global
   hotkey (`Win+Shift+F` by default) opens the dashboard on demand.

### Tests

```powershell
pytest
```

The test suite covers tagging, duplicate detection, cleanup rules, and path
safety, and runs on Linux/macOS as well as Windows — the Windows-only pieces
(pywin32 Explorer control, the `keyboard` hotkey, Recycle Bin deletion,
`msedge --app` window mode) live in isolated modules that no-op gracefully
on other platforms.

### Project layout

```
server/           Flask app, split into modules:
  config.py       Environment/config loading (.env via python-dotenv)
  db.py           SQLite schema and connection helpers
  calendar.py     Canvas/iCloud ICS fetching, caching, classification
  indexer.py      watchdog-based folder watching, hashing, text extraction
  tagging.py      rule / calendar / content / manual tag sources
  duplicates.py   exact (hash) and near (text similarity) duplicate detection
  fileops.py      rename/move/copy/delete + undo log
  pathsafety.py   refuses operations outside the watched folders
  explorer.py     pywin32 Shell.Application Explorer control
  rules.py        user-defined cleanup rules and suggestions
  versions.py     version snapshots, restore, diff
  archive.py      "Archive tag" physical sorting
  package.py      submission zip builder
  storage.py      storage overview stats
  api.py          all HTTP endpoints
  app.py          application factory / single server entry point
web/filesorter.html   self-contained frontend (no external CDNs/fonts)
tests/            pytest suite (tagging, duplicates, rules, path safety)
```

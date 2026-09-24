"""All HTTP endpoints, mounted at the app root so the existing /week.json
contract used by the dashboard keeps working unchanged."""
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, Response

from . import (
    archive,
    calendar as calendar_source,
    db,
    duplicates,
    events,
    explorer,
    fileops,
    package,
    pathsafety,
    rules,
    storage,
    tagging,
    versions,
)

bp = Blueprint("api", __name__)


# --- calendar / dashboard ------------------------------------------------

@bp.route("/week.json")
def week_json():
    week_events = calendar_source.get_week_events()
    return jsonify([calendar_source.event_to_json(e) for e in week_events])


@bp.route("/today/files")
def today_files():
    grouped = []
    for event in calendar_source.get_todays_events():
        with db.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.path, f.name FROM files f JOIN tags t ON f.hash = t.file_hash "
                "WHERE t.event_uid=? AND f.deleted=0",
                (event["uid"],),
            )
            files = [dict(r) for r in cur.fetchall()]
        grouped.append({"event": calendar_source.event_to_json(event), "files": files})
    return jsonify(grouped)


# --- files ----------------------------------------------------------------

def _file_to_json(row):
    d = dict(row)
    d["tags"] = tagging.get_tags(row["hash"])
    return d


@bp.route("/files")
def list_files():
    tag = request.args.get("tag")
    event = request.args.get("event")
    query = request.args.get("q")
    folder = request.args.get("folder")

    sql = "SELECT DISTINCT f.* FROM files f"
    conditions = ["f.deleted=0"]
    params = []
    if tag or event:
        sql += " JOIN tags t ON f.hash = t.file_hash"
        if tag:
            conditions.append("t.tag=?")
            params.append(tag)
        if event:
            conditions.append("t.event_uid=?")
            params.append(event)
    if query:
        conditions.append("f.name LIKE ?")
        params.append(f"%{query}%")
    if folder:
        conditions.append("f.path LIKE ?")
        params.append(f"{folder}%")

    sql += " WHERE " + " AND ".join(conditions)
    with db.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify([_file_to_json(r) for r in rows])


@bp.route("/files/<int:file_id>/raw")
def file_raw(file_id):
    with db.cursor() as cur:
        cur.execute("SELECT path FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    path = Path(row["path"])
    pathsafety.assert_path_allowed(path)
    return send_file(str(path))


@bp.route("/tags")
def list_tags():
    with db.cursor() as cur:
        cur.execute(
            "SELECT tag, COUNT(DISTINCT file_hash) AS count FROM tags GROUP BY tag ORDER BY tag"
        )
        return jsonify([dict(r) for r in cur.fetchall()])


@bp.route("/collections", methods=["GET", "POST"])
def collections():
    if request.method == "POST":
        payload = request.get_json(force=True)
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO collections (name, query) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET query=excluded.query",
                (payload["name"], payload.get("query", "")),
            )
        return jsonify({"ok": True})
    with db.cursor() as cur:
        cur.execute("SELECT * FROM collections ORDER BY name")
        return jsonify([dict(r) for r in cur.fetchall()])


@bp.route("/files/<int:file_id>/tags", methods=["PATCH"])
def patch_tags(file_id):
    payload = request.get_json(force=True)
    with db.cursor() as cur:
        cur.execute("SELECT hash FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    file_hash = row["hash"]
    for tag in payload.get("add", []):
        tagging.set_manual_tag(file_hash, tag)
    for tag in payload.get("remove", []):
        tagging.remove_tag(file_hash, tag)
    events.publish("tags-changed", {"file_id": file_id})
    return jsonify({"ok": True, "tags": tagging.get_tags(file_hash)})


# --- file operations --------------------------------------------------

@bp.route("/open/<int:file_id>", methods=["POST"])
def open_file(file_id):
    with db.cursor() as cur:
        cur.execute("SELECT path FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    path = Path(row["path"])
    pathsafety.assert_path_allowed(path)
    if explorer.IS_WINDOWS:
        import os
        os.startfile(str(path))
    return jsonify({"ok": True})


@bp.route("/files/<int:file_id>/reveal", methods=["POST"])
def reveal_file(file_id):
    with db.cursor() as cur:
        cur.execute("SELECT path FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    path = Path(row["path"])
    pathsafety.assert_path_allowed(path)
    explorer.open_folder(str(path.parent), select_paths=[str(path)])
    return jsonify({"ok": True})


@bp.route("/files/<int:file_id>/open-folder", methods=["POST"])
def open_folder_route(file_id):
    with db.cursor() as cur:
        cur.execute("SELECT path FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    path = Path(row["path"])
    pathsafety.assert_path_allowed(path)
    explorer.open_folder(str(path.parent))
    return jsonify({"ok": True})


@bp.route("/files/<int:file_id>/rename", methods=["POST"])
def rename_file_route(file_id):
    payload = request.get_json(force=True)
    try:
        result = fileops.rename_file(file_id, payload["new_name"])
    except (PermissionError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/files/move", methods=["POST"])
def move_files_route():
    payload = request.get_json(force=True)
    try:
        result = fileops.move_files(payload["ids"], payload["target_folder"])
    except (PermissionError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/files/copy", methods=["POST"])
def copy_files_route():
    payload = request.get_json(force=True)
    try:
        result = fileops.copy_files(payload["ids"], payload["target_folder"])
    except (PermissionError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/files/delete", methods=["POST"])
def delete_files_route():
    payload = request.get_json(force=True)
    try:
        result = fileops.delete_files(payload["ids"], payload.get("skip_confirmation", False))
    except (PermissionError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/folders", methods=["GET", "POST"])
def folders_route():
    from . import config
    if request.method == "POST":
        payload = request.get_json(force=True)
        new_folder = Path(payload["path"])
        pathsafety.assert_path_allowed(new_folder)
        new_folder.mkdir(parents=True, exist_ok=True)
        return jsonify({"ok": True})
    return jsonify({"watched": config.WATCHED_FOLDERS})


@bp.route("/undo", methods=["POST"])
def undo_route():
    return jsonify(fileops.undo_last())


# --- duplicates -------------------------------------------------------

@bp.route("/duplicates")
def duplicates_route():
    return jsonify(duplicates.find_exact_duplicates())


@bp.route("/duplicates/<hash_value>/resolve", methods=["POST"])
def resolve_duplicate(hash_value):
    payload = request.get_json(force=True)
    keep_id = payload["keep_id"]
    with db.cursor() as cur:
        cur.execute("SELECT * FROM files WHERE hash=? AND deleted=0", (hash_value,))
        rows = [dict(r) for r in cur.fetchall()]
    keeper = next((r for r in rows if r["id"] == keep_id), None)
    if not keeper:
        return jsonify({"error": "keep_id not in this duplicate group"}), 400
    others = [r for r in rows if r["id"] != keep_id]
    duplicates.merge_tags_into_keeper(keeper["hash"], [r["hash"] for r in others])
    result = fileops.delete_files([r["id"] for r in others])
    return jsonify(result)


@bp.route("/near-duplicates")
def near_duplicates_route():
    return jsonify(duplicates.find_near_duplicates())


@bp.route("/diff")
def diff_route():
    a = int(request.args.get("a"))
    b = int(request.args.get("b"))
    result = duplicates.diff_files(a, b)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


# --- explorer control ---------------------------------------------------

@bp.route("/explorer/windows")
def explorer_windows():
    return jsonify(explorer.list_windows())


@bp.route("/explorer/<int:hwnd>/navigate", methods=["POST"])
def explorer_navigate(hwnd):
    payload = request.get_json(force=True)
    return jsonify({"ok": explorer.navigate(hwnd, payload["folder"])})


@bp.route("/explorer/<int:hwnd>/select", methods=["POST"])
def explorer_select(hwnd):
    payload = request.get_json(force=True)
    return jsonify({"ok": explorer.select_in_window(hwnd, payload["paths"])})


@bp.route("/explorer/<int:hwnd>/close", methods=["POST"])
def explorer_close(hwnd):
    return jsonify({"ok": explorer.close_window(hwnd)})


@bp.route("/explorer/open", methods=["POST"])
def explorer_open():
    payload = request.get_json(force=True)
    ok = explorer.open_folder(payload["folder"], payload.get("select_paths"))
    return jsonify({"ok": ok})


@bp.route("/explorer/tag-view", methods=["POST"])
def explorer_tag_view():
    payload = request.get_json(force=True)
    folder = explorer.open_tag_view(payload["tag"])
    return jsonify({"folder": folder})


# --- rules / cleanup ----------------------------------------------------

@bp.route("/rules", methods=["GET", "POST", "DELETE"])
def rules_route():
    if request.method == "POST":
        payload = request.get_json(force=True)
        rule_id = rules.create_rule(
            payload["name"], payload.get("folder"), payload.get("pattern"),
            payload.get("age_days"), payload["action"], payload.get("target"),
            payload.get("enabled", True),
        )
        return jsonify({"id": rule_id})
    if request.method == "DELETE":
        payload = request.get_json(force=True)
        rules.delete_rule(payload["id"])
        return jsonify({"ok": True})
    return jsonify(rules.list_rules())


@bp.route("/cleanup")
def cleanup_route():
    return jsonify(rules.evaluate_rules())


@bp.route("/cleanup/apply", methods=["POST"])
def cleanup_apply():
    payload = request.get_json(force=True)
    with db.cursor() as cur:
        cur.execute(
            f"SELECT * FROM cleanup_suggestions WHERE id IN ({','.join('?' for _ in payload['ids'])})",
            payload["ids"],
        )
        suggestions = [dict(r) for r in cur.fetchall()]

    by_action = {}
    for s in suggestions:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM files WHERE hash=? AND deleted=0", (s["file_hash"],))
            row = cur.fetchone()
        if row:
            by_action.setdefault(s["action"], []).append(row["id"])

    results = {}
    try:
        for action, file_ids in by_action.items():
            if action == "delete":
                results["delete"] = fileops.delete_files(file_ids)
            elif action == "archive":
                target = str(archive.target_root() / "Archive")
                results["archive"] = fileops.move_files(file_ids, target)
    except (PermissionError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400

    rules.resolve_suggestions(payload["ids"])
    return jsonify(results)


# --- archive / package / storage ---------------------------------------

@bp.route("/archive/preview", methods=["POST"])
def archive_preview():
    payload = request.get_json(force=True)
    return jsonify(archive.preview_archive(payload["tag"], payload.get("template", archive.DEFAULT_TEMPLATE)))


@bp.route("/archive/apply", methods=["POST"])
def archive_apply():
    payload = request.get_json(force=True)
    return jsonify(archive.apply_archive(payload["tag"], payload.get("template", archive.DEFAULT_TEMPLATE)))


@bp.route("/files/<int:file_id>/versions")
def file_versions(file_id):
    with db.cursor() as cur:
        cur.execute("SELECT hash FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(versions.list_versions(row["hash"]))


@bp.route("/files/<int:file_id>/versions/<int:version_id>/restore", methods=["POST"])
def restore_version_route(file_id, version_id):
    with db.cursor() as cur:
        cur.execute("SELECT path FROM files WHERE id=?", (file_id,))
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    target = Path(row["path"])
    pathsafety.assert_path_allowed(target)
    versions.restore_version(version_id, target)
    return jsonify({"ok": True})


@bp.route("/package/preview", methods=["POST"])
def package_preview():
    payload = request.get_json(force=True)
    return jsonify(package.preview_package(payload["event_id"]))


@bp.route("/package/build", methods=["POST"])
def package_build():
    payload = request.get_json(force=True)
    zip_path = package.build_package(
        payload["event_id"], payload["file_ids"],
        payload.get("pattern", "{course}_{assignment}_{name}.{ext}"),
    )
    return jsonify({"zip_path": zip_path})


@bp.route("/storage")
def storage_route():
    return jsonify(storage.overview())


# --- events / status ------------------------------------------------------

@bp.route("/events")
def events_route():
    queue_obj = events.subscribe()
    return Response(events.stream(queue_obj), mimetype="text/event-stream")


@bp.route("/status")
def status_route():
    indexer = current_app.config["INDEXER"]
    return jsonify(indexer.status)

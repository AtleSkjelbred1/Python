"""Flask application factory. This is the single local background server:
it serves the dashboard's calendar proxy (/week.json, /today/files) as well
as the full file-sorting API, so only one process needs to run."""
import atexit

from flask import Flask
from flask_cors import CORS

from . import config, db
from .api import bp as api_bp
from .indexer import Indexer

_indexer = None


def _cors_origin_check(origin):
    if origin is None:
        return True
    if origin in ("null", "file://"):
        return True
    return origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")


def create_app():
    app = Flask(__name__)
    CORS(app, origins=_cors_origin_check, supports_credentials=False)

    db.init_db()

    global _indexer
    if _indexer is None:
        _indexer = Indexer(config.WATCHED_FOLDERS)
        _indexer.start()
        atexit.register(_indexer.stop)

    app.config["INDEXER"] = _indexer
    app.register_blueprint(api_bp)

    try:
        from . import hotkey
        hotkey.register_hotkey()
    except Exception:
        pass

    return app


def run():
    app = create_app()
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run()

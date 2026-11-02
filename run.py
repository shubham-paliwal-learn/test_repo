"""Entry point for the Trekking Management Application (TMA) Flask API.

Usage:
    python run.py                 # http://127.0.0.1:5000  (API + Vue UI)
    FLASK_CONFIG=production TMA_SECRET_KEY=... python run.py

NOTE: the application object is called ``trekking_app`` on purpose -- a name of
``app`` would shadow the ``app`` *package* imported from ``app.main`` and break
every later ``from app.xxx import ...`` with
``AttributeError: module 'app' has no attribute ...``.
"""
import os

from dotenv import load_dotenv

# Load .env (values already exported in the shell keep priority).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app.main import create_app  # noqa: E402  (import after env is loaded)

trekking_app = create_app()


@trekking_app.route("/")
def home():
    """Serve the Vue SPA (built with the Vite CLI, or the dev-source build)."""
    candidates = [
        os.path.join(trekking_app.root_path, "..", "frontend", "dist", "index.html"),
        os.path.join(trekking_app.root_path, "..", "frontend", "public", "index.html"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()
    return (
        "<h2>Trekking Management Application API is running</h2>"
        "<p>Endpoints are under <code>/api/...</code>. See README.md for the UI build steps.</p>"
    )


@trekking_app.route("/health")
def health():
    from app.services.cache_service import cache

    return {"status": "ok", "cache_backend": cache.backend}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False")
    trekking_app.run(host="0.0.0.0", port=port, debug=debug)

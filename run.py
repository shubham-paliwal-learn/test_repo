"""Entry point for the Trekking Management Application (TMA) Flask API.

Usage:
    python run.py                 # http://127.0.0.1:5000  (API + Vue UI)
    FLASK_CONFIG=production TMA_SECRET_KEY=... python run.py
"""
import os

from app.main import create_app

app = create_app()


@app.route("/")
def home():
    """Serve the Vue SPA (built with the Vite CLI, or the dev-source build)."""
    candidates = [
        os.path.join(app.root_path, "..", "frontend", "dist", "index.html"),
        os.path.join(app.root_path, "..", "frontend", "public", "index.html"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()
    return (
        "<h2>Trekking Management Application API is running</h2>"
        "<p>Endpoints are under <code>/api/...</code>. See README.md for the UI build steps.</p>"
    )


@app.route("/health")
def health():
    from app.services.cache_service import cache

    return {"status": "ok", "cache_backend": cache.backend}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False")
    app.run(host="0.0.0.0", port=port, debug=debug)

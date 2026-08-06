"""Application factory for PanoCOTA."""

from __future__ import annotations

from flask import Flask

from .routes import register_routes
from .settings import BASE_DIR
from .storage import ensure_paths


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    ensure_paths()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    register_routes(app)
    return app

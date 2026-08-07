"""Thin Flask entrypoint for PanoCOTA."""

from __future__ import annotations

import logging
import os
import sys

from flask import cli as flask_cli

from panocore.app_factory import create_app


if sys.version_info[:2] != (3, 13):
    raise RuntimeError(
        f"PanoCoTA requires Python 3.13.x. Detected Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}."
    )

app = create_app()


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with common truthy values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def run() -> None:
    """Run the development server using environment-configured host and port."""
    host = os.getenv("PANOCOTA_HOST", "0.0.0.0")
    port = int(os.getenv("PANOCOTA_PORT", "5000"))
    debug = _env_flag("PANOCOTA_DEBUG", default=False)
    use_reloader = _env_flag("PANOCOTA_RELOAD", default=debug)
    verbose = _env_flag("PANOCOTA_VERBOSE", default=debug)

    if not verbose:
        flask_cli.show_server_banner = lambda *_args, **_kwargs: None
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        app.logger.setLevel(logging.WARNING)
        print("######################################################")
        print("######################################################")
        print("\n")
        print(f"Welcome to PanoCoTA!")
        print("\n")
        print("######################################################")
        print("######################################################")
        print("\n")
        print(f"To open the editor: http://127.0.0.1:{port}")
        print(f"To open the viewer: http://127.0.0.1:{port}/viewer")
    
    app.run(debug=debug, use_reloader=use_reloader, host=host, port=port)


if __name__ == "__main__":
    run()

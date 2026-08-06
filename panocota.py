"""Thin Flask entrypoint for PanoCOTA."""

from __future__ import annotations

import os

from panocore.app_factory import create_app

app = create_app()


def run() -> None:
    """Run the development server using environment-configured host and port."""
    host = os.getenv("PANOCOTA_HOST", "0.0.0.0")
    port = int(os.getenv("PANOCOTA_PORT", "5000"))
    app.run(debug=True, host=host, port=port)


if __name__ == "__main__":
    run()

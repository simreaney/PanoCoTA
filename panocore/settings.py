"""Project-wide backend settings and paths."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOUR_DIR = BASE_DIR / "tour_data"
TOUR_FILE = TOUR_DIR / "tour.json"
IMAGES_360_DIR = BASE_DIR / "static" / "images_360"
IMAGES_2D_DIR = BASE_DIR / "static" / "images_2d"
LEGACY_IMAGES_DIR = BASE_DIR / "static" / "images"
# Legacy alias retained for compatibility with older code paths.
IMAGES_DIR = IMAGES_360_DIR
DATA_DIR = BASE_DIR / "static" / "data"
GRAPHS_DIR = BASE_DIR / "static" / "graphs"

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DATA_EXTENSIONS = {"csv"}

# Increase this value whenever graph rendering style changes so cached assets refresh.
GRAPH_RENDER_VERSION = 10

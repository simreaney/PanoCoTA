"""Tour and file storage helpers."""

from __future__ import annotations

import json
from pathlib import Path

from werkzeug.utils import secure_filename

from .settings import (
    ALLOWED_DATA_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    DATA_DIR,
    GRAPHS_DIR,
    LEGACY_IMAGES_DIR,
    IMAGES_2D_DIR,
    IMAGES_360_DIR,
    TOUR_DIR,
    TOUR_FILE,
)


GRAPH_CACHE_SIGNATURE_FILENAME = ".cache_signature"


def ensure_paths() -> None:
    """Create required data directories if they do not exist."""
    TOUR_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_360_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_2D_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_tour_name(name: str | None) -> str:
    """Normalize a user-provided tour name to a safe basename without extension."""
    raw = (name or "").strip()
    if raw.endswith(".json"):
        raw = raw[:-5]

    safe = secure_filename(raw)
    return safe or TOUR_FILE.stem


def tour_path(name: str | None = None) -> Path:
    """Return filesystem path for a named tour JSON file."""
    return TOUR_DIR / f"{normalize_tour_name(name)}.json"


def list_tour_names() -> list[str]:
    """Return sorted list of available tour names in storage directory."""
    return sorted(path.stem for path in TOUR_DIR.glob("*.json") if path.is_file())


def panorama_dir_for_tour(name: str | None) -> Path:
    """Return 360 panorama storage directory path for a named tour."""
    return IMAGES_360_DIR / normalize_tour_name(name)


def image_2d_dir_for_tour(name: str | None) -> Path:
    """Return 2D image storage directory path for a named tour."""
    return IMAGES_2D_DIR / normalize_tour_name(name)


def image_dir_for_tour(name: str | None) -> Path:
    """Legacy alias for panorama directory path."""
    return panorama_dir_for_tour(name)


def data_dir_for_tour(name: str | None) -> Path:
    """Return CSV data storage directory path for a named tour."""
    return DATA_DIR / normalize_tour_name(name)


def graph_dir_for_tour(name: str | None) -> Path:
    """Return generated graph storage directory path for a named tour."""
    return GRAPHS_DIR / normalize_tour_name(name)


def clear_graph_cache_for_tour(name: str | None) -> int:
    """Delete cached graph files for a named tour and return number removed."""
    graph_dir = graph_dir_for_tour(name)
    if not graph_dir.exists():
        return 0

    removed = 0
    for path in graph_dir.iterdir():
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def graph_cache_signature_path_for_tour(name: str | None) -> Path:
    """Return metadata file path storing graph cache signature for a tour."""
    return graph_dir_for_tour(name) / GRAPH_CACHE_SIGNATURE_FILENAME


def read_graph_cache_signature_for_tour(name: str | None) -> str | None:
    """Read stored graph cache signature for a tour, if present."""
    marker = graph_cache_signature_path_for_tour(name)
    if not marker.exists() or not marker.is_file():
        return None
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def write_graph_cache_signature_for_tour(name: str | None, signature: str) -> None:
    """Persist graph cache signature metadata for a tour."""
    graph_dir = graph_dir_for_tour(name)
    graph_dir.mkdir(parents=True, exist_ok=True)
    marker = graph_cache_signature_path_for_tour(name)
    marker.write_text(str(signature or "").strip(), encoding="utf-8")


def ensure_tour_asset_dirs(name: str | None) -> tuple[Path, Path, Path, Path]:
    """Ensure per-tour panorama/2D/data/graph directories exist and return them."""
    panorama_dir = panorama_dir_for_tour(name)
    image_2d_dir = image_2d_dir_for_tour(name)
    data_dir = data_dir_for_tour(name)
    graph_dir = graph_dir_for_tour(name)
    panorama_dir.mkdir(parents=True, exist_ok=True)
    image_2d_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    return panorama_dir, image_2d_dir, data_dir, graph_dir


def _list_images_in_dir(image_dir: Path) -> list[str]:
    """List allowed image filenames in a given directory."""
    if not image_dir.exists():
        return []
    return sorted(
        [
            path.name
            for path in image_dir.iterdir()
            if path.is_file() and is_allowed_image(path.name)
        ]
    )


def list_panorama_images_for_tour(name: str | None) -> list[str]:
    """List allowed 360 panorama filenames stored for a specific tour."""
    primary = set(_list_images_in_dir(panorama_dir_for_tour(name)))
    legacy = set(_list_images_in_dir(LEGACY_IMAGES_DIR / normalize_tour_name(name)))
    return sorted(primary | legacy)


def list_2d_images_for_tour(name: str | None) -> list[str]:
    """List allowed 2D image filenames stored for a specific tour."""
    return _list_images_in_dir(image_2d_dir_for_tour(name))


def list_images_for_tour(name: str | None) -> list[str]:
    """Legacy alias for listing panorama image filenames."""
    return list_panorama_images_for_tour(name)


def list_csvs_for_tour(name: str | None) -> list[str]:
    """List CSV filenames stored for a specific tour."""
    data_dir = data_dir_for_tour(name)
    if not data_dir.exists():
        return []
    return sorted(
        [
            path.name
            for path in data_dir.glob("*.csv")
            if path.is_file()
        ]
    )


def delete_tour(name: str | None) -> bool:
    """Delete a named tour file if it exists and return whether deletion occurred."""
    selected_file = tour_path(name)
    if not selected_file.exists():
        return False

    selected_file.unlink()
    return True


def load_tour(name: str | None = None) -> dict:
    """Load a persisted tour JSON file by name."""
    selected_file = tour_path(name)
    if not selected_file.exists():
        raise FileNotFoundError("Saved tour file does not exist.")

    with selected_file.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_tour(tour_payload: dict, name: str | None = None) -> str:
    """Persist the provided tour payload to a named tour file and return normalized name."""
    normalized_name = normalize_tour_name(name)
    target_file = tour_path(normalized_name)
    with target_file.open("w", encoding="utf-8") as handle:
        json.dump(tour_payload, handle, indent=2)
    return normalized_name


def is_allowed_image(filename: str) -> bool:
    """Return True when filename has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def is_allowed_data_file(filename: str) -> bool:
    """Return True when filename has an allowed data-file extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DATA_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename using Werkzeug sanitization."""
    return secure_filename(filename)


def ensure_tour_file_exists() -> None:
    """Ensure a tour file exists on disk; legacy no-op retained for compatibility."""


def write_uploaded_file(file_obj, target_path: Path) -> None:
    """Save a Flask uploaded file object to the given path."""
    file_obj.save(target_path)

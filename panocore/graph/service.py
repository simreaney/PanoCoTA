"""Graph asset generation service."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..settings import DATA_DIR, GRAPH_RENDER_VERSION
from ..storage import data_dir_for_tour, graph_dir_for_tour, is_allowed_data_file, sanitize_filename
from .parsing import derive_y_axis_label, extract_multi_series, load_csv_rows
from .render_matplotlib import MATPLOTLIB_AVAILABLE, generate_with_matplotlib
from .render_pillow import generate_with_pillow


def _clean_graph_inputs(
    csv_name: str,
    x_col: str | None,
    y_cols: list[str] | str | None,
    animate: bool,
) -> tuple[str, str, list[str], bool]:
    """Validate and normalize user graph-query input values."""
    safe_name = sanitize_filename(csv_name)
    if not safe_name:
        raise ValueError("CSV filename is required.")
    if not is_allowed_data_file(safe_name):
        raise ValueError("CSV file must end with .csv.")

    raw_y_cols: list[str]
    if isinstance(y_cols, list):
        raw_y_cols = y_cols
    elif isinstance(y_cols, str):
        raw_y_cols = [y_cols]
    else:
        raw_y_cols = []

    cleaned_y_cols = [value.strip() for value in raw_y_cols if value and value.strip()]
    if not cleaned_y_cols:
        raise ValueError("At least one y column is required.")
    if len(cleaned_y_cols) > 3:
        raise ValueError("A maximum of three y columns is supported.")

    return safe_name, (x_col or "").strip(), cleaned_y_cols, animate


def _normalize_size(size: str | None) -> str:
    """Normalize requested render size to one of s, m, or l."""
    normalized = (size or "m").strip().lower()
    if normalized not in {"s", "m", "l"}:
        raise ValueError("size must be one of: s, m, l")
    return normalized


def _normalize_animation_speed(animation_speed: float | int | str | None) -> float:
    """Normalize animation speed multiplier to a safe positive range."""
    try:
        value = float(animation_speed if animation_speed is not None else 1.0)
    except (TypeError, ValueError):
        raise ValueError("animationSpeed must be a positive number.")
    if value <= 0:
        raise ValueError("animationSpeed must be greater than zero.")
    return max(0.25, min(4.0, value))


def _normalize_subplot_types(subplot_types: list[str] | None, count: int) -> list[str]:
    """Normalize per-subplot graph types to line/scatter/bar."""
    allowed = {"line", "scatter", "bar"}
    values = [str(value or "").strip().lower() for value in (subplot_types or [])]
    if values and len(values) != count:
        raise ValueError("Number of plotType values must match subplot count.")

    normalized: list[str] = []
    for idx in range(count):
        candidate = values[idx] if idx < len(values) and values[idx] else "line"
        if candidate not in allowed:
            raise ValueError("plotType must be one of: line, scatter, bar")
        normalized.append(candidate)
    return normalized


def _parse_bool(value: bool | str | int | None) -> bool:
    """Parse mixed boolean-like inputs from query/service call layers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


def _normalize_inverted_bars(inverted_bars: list[bool | str | int] | None, count: int) -> list[bool]:
    """Normalize per-subplot inverted-bar flags."""
    values = list(inverted_bars or [])
    if values and len(values) != count:
        raise ValueError("Number of invertBar values must match subplot count.")

    normalized: list[bool] = []
    for idx in range(count):
        normalized.append(_parse_bool(values[idx]) if idx < len(values) else False)
    return normalized


def _validate_subplot_options(subplot_types: list[str], inverted_bars: list[bool]) -> None:
    """Ensure subplot option combinations are semantically valid."""
    for idx, plot_type in enumerate(subplot_types):
        if plot_type != "bar" and inverted_bars[idx]:
            raise ValueError("invertBar can only be true when plotType is 'bar'.")


def _build_graph_filename(
    csv_path: Path,
    x_col: str,
    y_cols: list[str],
    subplot_types: list[str],
    inverted_bars: list[bool],
    animate: bool,
    animation_speed: float,
    renderer: str,
    size: str,
) -> str:
    """Create deterministic graph filename based on CSV and render inputs."""
    seed = (
        f"{GRAPH_RENDER_VERSION}|{csv_path.name}|{x_col}|{'|'.join(y_cols)}|"
        f"{'|'.join(subplot_types)}|{'|'.join(str(flag) for flag in inverted_bars)}|"
        f"{animate}|{animation_speed:.3f}|{renderer}|{size}|{csv_path.stat().st_mtime_ns}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18]
    ext = "gif" if animate else "png"
    return f"graph_{digest}.{ext}"


def generate_graph_asset(
    csv_name: str,
    x_col: str | None,
    y_cols: list[str] | str | None,
    animate: bool,
    y_label: str | None = None,
    y_unit: str | None = None,
    subplot_types: list[str] | None = None,
    inverted_bars: list[bool | str | int] | None = None,
    animation_speed: float | int | str | None = 1.0,
    renderer: str = "auto",
    size: str = "m",
    tour_name: str = "tour",
) -> str:
    """Generate graph asset and return filename of cached/created image."""
    safe_csv, safe_x, safe_y_cols, animate = _clean_graph_inputs(csv_name, x_col, y_cols, animate)
    renderer = (renderer or "auto").strip().lower()
    size = _normalize_size(size)
    animation_speed = _normalize_animation_speed(animation_speed)
    if renderer not in {"auto", "matplotlib", "pillow"}:
        raise ValueError("renderer must be one of: auto, matplotlib, pillow")

    normalized_subplot_types = _normalize_subplot_types(subplot_types, len(safe_y_cols))
    normalized_inverted_bars = _normalize_inverted_bars(inverted_bars, len(safe_y_cols))
    _validate_subplot_options(normalized_subplot_types, normalized_inverted_bars)

    csv_path = data_dir_for_tour(tour_name) / safe_csv
    if not csv_path.exists():
        # Backward-compatibility for legacy tours that referenced global data files.
        csv_path = DATA_DIR / safe_csv
    if not csv_path.exists():
        raise ValueError(f"CSV file '{safe_csv}' was not found in /static/data.")

    graph_filename = _build_graph_filename(
        csv_path,
        safe_x,
        safe_y_cols,
        normalized_subplot_types,
        normalized_inverted_bars,
        animate,
        animation_speed,
        renderer,
        size,
    )
    graph_dir = graph_dir_for_tour(tour_name)
    graph_dir.mkdir(parents=True, exist_ok=True)
    output_path = graph_dir / graph_filename
    if output_path.exists():
        return graph_filename

    fields, rows = load_csv_rows(csv_path)
    x_values, y_series, _, x_is_datetime = extract_multi_series(fields, rows, safe_x, safe_y_cols)
    if len(safe_y_cols) == 1:
        y_axis_labels = [derive_y_axis_label(safe_y_cols[0], y_label, y_unit)]
    else:
        y_axis_labels = [derive_y_axis_label(y_col, None, None) for y_col in safe_y_cols]

    subplot_count = len(safe_y_cols)

    if renderer == "matplotlib":
        if not MATPLOTLIB_AVAILABLE:
            raise ValueError("Matplotlib renderer is not available in this environment.")
        try:
            generate_with_matplotlib(
                output_path,
                x_values,
                y_series,
                y_axis_labels,
                normalized_subplot_types,
                normalized_inverted_bars,
                animate,
                animation_speed,
                size,
            )
            return graph_filename
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Matplotlib renderer failed: {exc}") from exc

    if renderer == "auto" and MATPLOTLIB_AVAILABLE:
        try:
            generate_with_matplotlib(
                output_path,
                x_values,
                y_series,
                y_axis_labels,
                normalized_subplot_types,
                normalized_inverted_bars,
                animate,
                animation_speed,
                size,
            )
            return graph_filename
        except ValueError:
            raise
        except Exception:
            pass

    if subplot_count > 1:
        raise ValueError("Multiple subplots require the matplotlib renderer.")

    if normalized_subplot_types[0] != "line" or normalized_inverted_bars[0]:
        if renderer == "pillow":
            raise ValueError("Pillow renderer only supports line plots without inverted bars.")

    generate_with_pillow(
        output_path,
        x_values,
        y_series[0],
        y_axis_labels[0],
        x_is_datetime,
        animate,
        size,
        animation_speed,
    )
    return graph_filename

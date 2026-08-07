"""Graph asset generation service."""

from __future__ import annotations

import hashlib
import platform
from importlib import metadata
from pathlib import Path

from ..settings import DATA_DIR, GRAPH_RENDER_VERSION
from ..storage import data_dir_for_tour, graph_dir_for_tour, is_allowed_data_file, sanitize_filename
from .parsing import derive_y_axis_label, extract_multi_series, load_csv_rows
from .render_matplotlib import MATPLOTLIB_AVAILABLE, generate_with_matplotlib
from .render_pillow import generate_with_pillow


def get_graph_cache_signature() -> str:
    """Return a deterministic signature of graph renderer code and settings."""
    signature_parts = [f"render_version={GRAPH_RENDER_VERSION}", f"python={platform.python_version()}"]
    try:
        signature_parts.append(f"matplotlib={metadata.version('matplotlib')}")
    except metadata.PackageNotFoundError:
        signature_parts.append("matplotlib=missing")

    files_to_hash = [
        Path(__file__),
        Path(__file__).with_name("render_matplotlib.py"),
        Path(__file__).with_name("render_pillow.py"),
        Path(__file__).with_name("parsing.py"),
        Path(__file__).with_name("common.py"),
        Path(__file__).resolve().parents[1] / "settings.py",
    ]

    digest = hashlib.sha256()
    for value in signature_parts:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")

    for path in files_to_hash:
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\n")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\n")

    return digest.hexdigest()


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
    """Normalize animation seconds-per-frame input to a safe positive range."""
    try:
        value = float(animation_speed if animation_speed is not None else 0.1)
    except (TypeError, ValueError):
        raise ValueError("animationSpeed must be a positive number.")
    if value <= 0:
        raise ValueError("animationSpeed must be greater than zero.")
    return max(0.001, min(30.0, value))


def _normalize_max_points(max_points: int | str | None) -> int | None:
    """Normalize optional max-points cap used for fast preview rendering."""
    if max_points is None:
        return None
    text = str(max_points).strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        raise ValueError("maxPoints must be an integer greater than 10.")
    if parsed == 0:
        return None
    if parsed < 10:
        raise ValueError("maxPoints must be an integer greater than 10.")
    return parsed


def _normalize_max_animation_frames(max_animation_frames: int | str | None) -> int | None:
    """Normalize optional animation frame cap; None disables frame decimation."""
    if max_animation_frames is None:
        return None
    text = str(max_animation_frames).strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        raise ValueError("maxAnimationFrames must be a positive integer.")
    if parsed <= 0:
        return None
    return parsed


def _normalize_animation_loop_count(animation_loop_count: int | str | None) -> int:
    """Normalize GIF animation loop count (0 means infinite looping)."""
    if animation_loop_count is None:
        return 0
    text = str(animation_loop_count).strip()
    if not text:
        return 0
    try:
        parsed = int(text)
    except ValueError:
        raise ValueError("animationLoopCount must be a non-negative integer.")
    if parsed < 0:
        raise ValueError("animationLoopCount must be a non-negative integer.")
    return parsed


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


def _normalize_subplot_colors(subplot_colors: list[str] | None, count: int) -> list[str]:
    """Normalize per-subplot colors to common named colors."""
    allowed = {
        "red",
        "blue",
        "green",
        "orange",
        "purple",
        "teal",
        "brown",
        "black",
        "gray",
        "pink",
    }
    defaults = ["red", "teal", "orange"]
    values = [str(value or "").strip().lower() for value in (subplot_colors or [])]
    if values and len(values) != count:
        raise ValueError("Number of color values must match subplot count.")

    normalized: list[str] = []
    for idx in range(count):
        candidate = values[idx] if idx < len(values) else ""
        if candidate in allowed:
            normalized.append(candidate)
        elif candidate:
            raise ValueError("color must be one of: red, blue, green, orange, purple, teal, brown, black, gray, pink")
        else:
            normalized.append(defaults[idx % len(defaults)])
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
    """Ensure subplot option arrays align with each subplot."""
    if len(subplot_types) != len(inverted_bars):
        raise ValueError("plotType and invertBar option counts must match subplot count.")


def _build_graph_filename(
    csv_path: Path,
    x_col: str,
    y_cols: list[str],
    subplot_types: list[str],
    subplot_colors: list[str],
    inverted_bars: list[bool],
    animate: bool,
    animation_speed: float,
    renderer: str,
    size: str,
    max_points: int | None,
    max_animation_frames: int | None,
    animation_loop_count: int,
    animation_time_budget_seconds: float | None,
) -> str:
    """Create deterministic graph filename based on CSV and render inputs."""
    seed = (
        f"{GRAPH_RENDER_VERSION}|{csv_path.name}|{x_col}|{'|'.join(y_cols)}|"
        f"{'|'.join(subplot_types)}|{'|'.join(subplot_colors)}|{'|'.join(str(flag) for flag in inverted_bars)}|"
        f"{animate}|{animation_speed:.3f}|{renderer}|{size}|{max_points or 0}|{max_animation_frames or 0}|{animation_loop_count}|{animation_time_budget_seconds or 0}|{csv_path.stat().st_mtime_ns}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18]
    ext = "gif" if animate else "png"
    return f"graph_{digest}.{ext}"


def _generate_graph_asset_impl(
    csv_name: str,
    x_col: str | None,
    y_cols: list[str] | str | None,
    animate: bool,
    y_label: str | None = None,
    y_unit: str | None = None,
    subplot_types: list[str] | None = None,
    subplot_colors: list[str] | None = None,
    inverted_bars: list[bool | str | int] | None = None,
    animation_speed: float | int | str | None = 0.1,
    renderer: str = "auto",
    size: str = "m",
    tour_name: str = "tour",
    max_points: int | str | None = None,
    max_animation_frames: int | str | None = 180,
    animation_loop_count: int | str | None = 0,
    animation_time_budget_seconds: float | int | str | None = None,
    force_regenerate: bool = False,
) -> tuple[str, bool, int, int]:
    """Generate graph asset and return filename plus preview sampling metadata."""
    safe_csv, safe_x, safe_y_cols, animate = _clean_graph_inputs(csv_name, x_col, y_cols, animate)
    renderer = (renderer or "auto").strip().lower()
    size = _normalize_size(size)
    max_points = _normalize_max_points(max_points)
    max_animation_frames = _normalize_max_animation_frames(max_animation_frames)
    animation_loop_count = _normalize_animation_loop_count(animation_loop_count)
    animation_time_budget_seconds = None if animation_time_budget_seconds is None else float(animation_time_budget_seconds)
    animation_speed = _normalize_animation_speed(animation_speed)
    if renderer not in {"auto", "matplotlib", "pillow"}:
        raise ValueError("renderer must be one of: auto, matplotlib, pillow")

    normalized_subplot_types = _normalize_subplot_types(subplot_types, len(safe_y_cols))
    normalized_subplot_colors = _normalize_subplot_colors(subplot_colors, len(safe_y_cols))
    normalized_inverted_bars = _normalize_inverted_bars(inverted_bars, len(safe_y_cols))
    _validate_subplot_options(normalized_subplot_types, normalized_inverted_bars)
    if len(safe_y_cols) > 1 and renderer == "pillow" and MATPLOTLIB_AVAILABLE:
        # Backward compatibility: old hotspot payloads may carry renderer='pillow'.
        renderer = "matplotlib"

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
        normalized_subplot_colors,
        normalized_inverted_bars,
        animate,
        animation_speed,
        renderer,
        size,
        max_points,
        max_animation_frames,
        animation_loop_count,
        animation_time_budget_seconds,
    )
    graph_dir = graph_dir_for_tour(tour_name)
    graph_dir.mkdir(parents=True, exist_ok=True)
    output_path = graph_dir / graph_filename

    sampled = False
    original_points = 0
    plotted_points = 0

    if output_path.exists() and not force_regenerate:
        fields, rows = load_csv_rows(csv_path)
        x_values_existing, _, _, _ = extract_multi_series(fields, rows, safe_x, safe_y_cols)
        original_points = len(x_values_existing)
        plotted_points = original_points
        if max_points is not None and original_points > max_points:
            sampled = True
            plotted_points = max_points
        return graph_filename, sampled, original_points, plotted_points

    fields, rows = load_csv_rows(csv_path)
    x_values, y_series, _, x_is_datetime = extract_multi_series(fields, rows, safe_x, safe_y_cols)
    original_points = len(x_values)
    plotted_points = original_points
    if max_points is not None and len(x_values) > max_points:
        # Uniform index sampling dramatically reduces matplotlib draw time on large files.
        sampled = True
        sample_count = max_points
        span = len(x_values) - 1
        indices = sorted({round(i * span / (sample_count - 1)) for i in range(sample_count)})
        x_values = [x_values[idx] for idx in indices]
        y_series = [[series[idx] for idx in indices] for series in y_series]
        plotted_points = len(x_values)

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
                normalized_subplot_colors,
                normalized_inverted_bars,
                animate,
                animation_speed,
                size,
                max_animation_frames,
                animation_loop_count,
                animation_time_budget_seconds,
            )
            return graph_filename, sampled, original_points, plotted_points
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
                normalized_subplot_colors,
                normalized_inverted_bars,
                animate,
                animation_speed,
                size,
                max_animation_frames,
                animation_loop_count,
                animation_time_budget_seconds,
            )
            return graph_filename, sampled, original_points, plotted_points
        except ValueError:
            raise
        except Exception:
            pass

    if subplot_count > 1:
        raise ValueError("Multiple subplots require the matplotlib renderer.")

    if normalized_subplot_types[0] != "line":
        if renderer == "pillow":
            raise ValueError("Pillow renderer only supports line plots.")

    generate_with_pillow(
        output_path,
        x_values,
        y_series[0],
        y_axis_labels[0],
        x_is_datetime,
        animate,
        size,
        animation_speed,
        normalized_inverted_bars[0],
        normalized_subplot_colors[0],
    )
    return graph_filename, sampled, original_points, plotted_points


def generate_graph_asset(
    csv_name: str,
    x_col: str | None,
    y_cols: list[str] | str | None,
    animate: bool,
    y_label: str | None = None,
    y_unit: str | None = None,
    subplot_types: list[str] | None = None,
    subplot_colors: list[str] | None = None,
    inverted_bars: list[bool | str | int] | None = None,
    animation_speed: float | int | str | None = 0.1,
    renderer: str = "auto",
    size: str = "m",
    tour_name: str = "tour",
    max_points: int | str | None = None,
    max_animation_frames: int | str | None = 180,
    animation_loop_count: int | str | None = 0,
    animation_time_budget_seconds: float | int | str | None = None,
    force_regenerate: bool = False,
) -> str:
    """Generate graph asset and return filename of cached/created image."""
    graph_filename, _, _, _ = _generate_graph_asset_impl(
        csv_name,
        x_col,
        y_cols,
        animate,
        y_label,
        y_unit,
        subplot_types,
        subplot_colors,
        inverted_bars,
        animation_speed,
        renderer,
        size,
        tour_name,
        max_points,
        max_animation_frames,
        animation_loop_count,
        animation_time_budget_seconds,
        force_regenerate,
    )
    return graph_filename


def generate_graph_asset_with_info(
    csv_name: str,
    x_col: str | None,
    y_cols: list[str] | str | None,
    animate: bool,
    y_label: str | None = None,
    y_unit: str | None = None,
    subplot_types: list[str] | None = None,
    subplot_colors: list[str] | None = None,
    inverted_bars: list[bool | str | int] | None = None,
    animation_speed: float | int | str | None = 0.1,
    renderer: str = "auto",
    size: str = "m",
    tour_name: str = "tour",
    max_points: int | str | None = None,
    max_animation_frames: int | str | None = 180,
    animation_loop_count: int | str | None = 0,
    animation_time_budget_seconds: float | int | str | None = None,
    force_regenerate: bool = False,
) -> dict:
    """Generate graph asset and return filename plus preview sampling metadata."""
    graph_filename, sampled, original_points, plotted_points = _generate_graph_asset_impl(
        csv_name,
        x_col,
        y_cols,
        animate,
        y_label,
        y_unit,
        subplot_types,
        subplot_colors,
        inverted_bars,
        animation_speed,
        renderer,
        size,
        tour_name,
        max_points,
        max_animation_frames,
        animation_loop_count,
        animation_time_budget_seconds,
        force_regenerate,
    )
    return {
        "filename": graph_filename,
        "sampled": sampled,
        "originalPoints": original_points,
        "plottedPoints": plotted_points,
    }

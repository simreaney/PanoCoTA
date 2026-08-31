"""Matplotlib graph renderer."""

from __future__ import annotations

import math
from time import perf_counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

MATPLOTLIB_AVAILABLE = False
plt: Any = None
FuncAnimation: Any = None
PillowWriter: Any = None
mdates: Any = None

try:
    import matplotlib
    from matplotlib import dates as mdates
    from matplotlib import pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    matplotlib.use("Agg")
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


def _coerce_x_numeric(x_values: list) -> list[float]:
    """Convert x values to numeric positions for axis bounds.

    Handles mixed lists (e.g. datetimes from one series and floats from
    another) by coercing each value individually.
    """
    if not x_values:
        return []

    coerced: list[float] = []
    for value in x_values:
        try:
            if isinstance(value, datetime):
                numeric = float(value.timestamp())
            else:
                numeric = float(value)
        except (TypeError, ValueError):
            numeric = float("nan")
        if not math.isfinite(numeric):
            # Skip non-finite values so axis bounds stay finite.
            continue
        coerced.append(numeric)
    return coerced


def _compute_bar_widths(x_values: list) -> list[float]:
    """Compute non-overlapping bar widths from local x-axis spacing."""
    count = len(x_values)
    if count == 0:
        return []
    if count == 1:
        return [0.8]

    x_is_datetime = isinstance(x_values[0], datetime)
    if x_is_datetime and mdates is not None:
        x_numeric = [float(value) for value in mdates.date2num(x_values)]
    else:
        x_numeric = _coerce_x_numeric(x_values)

    if len(x_numeric) < 2:
        return [0.8 for _ in x_values]

    sorted_x = sorted(x_numeric)
    positive_gaps = [
        sorted_x[idx + 1] - sorted_x[idx]
        for idx in range(len(sorted_x) - 1)
        if (sorted_x[idx + 1] - sorted_x[idx]) > 0
    ]
    default_gap = min(positive_gaps) if positive_gaps else 1.0

    widths: list[float] = []
    for idx, current_x in enumerate(x_numeric):
        left_gap = None
        for left_idx in range(idx - 1, -1, -1):
            gap = current_x - x_numeric[left_idx]
            if gap > 0:
                left_gap = gap
                break

        right_gap = None
        for right_idx in range(idx + 1, count):
            gap = x_numeric[right_idx] - current_x
            if gap > 0:
                right_gap = gap
                break

        if left_gap is not None and right_gap is not None:
            local_gap = min(left_gap, right_gap)
        elif left_gap is not None:
            local_gap = left_gap
        elif right_gap is not None:
            local_gap = right_gap
        else:
            local_gap = default_gap

        widths.append(max(local_gap * 0.15, local_gap * 0.82))

    return widths


def _enforce_min_visible_bar_widths(
    x_values: list,
    widths: list[float],
    fig_width_inches: float,
    dpi: int,
    min_pixels: float = 1.4,
) -> list[float]:
    """Ensure bars are at least a few screen pixels wide even for dense full-data renders."""
    if not x_values or not widths:
        return widths

    x_numeric = _coerce_x_numeric(x_values)
    if len(x_numeric) < 2:
        return widths

    x_min = min(x_numeric)
    x_max = max(x_numeric)
    x_span = x_max - x_min
    if math.isclose(x_span, 0.0):
        return widths

    # Approximate drawable axis width from figure width to convert pixel minimum into data units.
    axis_pixel_width = max(fig_width_inches * dpi * 0.78, 1.0)
    min_width_data = (x_span / axis_pixel_width) * max(min_pixels, 0.5)
    max_width_data = x_span * 0.45

    if min_width_data <= 0:
        return widths

    return [min(max(width, min_width_data), max_width_data) for width in widths]


def _finite_values(values: list) -> list[float]:
    """Filter out nan/inf so axis limits stay finite."""
    return [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]


def _compute_y_limits(y_values: list[float]) -> tuple[float, float]:
    """Compute y-axis limits with +/-10% padding and a zero floor for non-negative data."""
    finite = _finite_values(y_values)
    if not finite:
        return (-1.0, 1.0)

    min_value = min(finite)
    max_value = max(finite)

    upper = max_value + (abs(max_value) * 0.1)
    if min_value < 0:
        lower = min_value - (abs(min_value) * 0.1)
    else:
        lower = 0.0

    if math.isclose(lower, upper):
        delta = abs(max_value) * 0.1 or 1.0
        lower -= delta
        upper += delta
    return (lower, upper)


def _normalize_x_series(x_values: list, subplot_count: int) -> list[list]:
    """Return per-subplot x arrays. Accepts a flat shared list or a list of lists."""
    if subplot_count == 0:
        return []
    # Detect list-of-lists (per-subplot x) vs flat list (shared x).
    if x_values and isinstance(x_values[0], (list, tuple)):
        per_subplot = [list(series) for series in x_values]
        if len(per_subplot) != subplot_count:
            raise ValueError("Number of per-subplot x series must match subplot count.")
        return per_subplot
    # Flat shared x: replicate for every subplot.
    return [list(x_values) for _ in range(subplot_count)]


def generate_with_matplotlib(
    output_path: Path,
    x_values: list,
    y_series: list[list[float]],
    y_labels: list[str],
    subplot_types: list[str],
    subplot_colors: list[str],
    inverted_bars: list[bool],
    animate: bool,
    animation_speed: float = 1.0,
    size: str = "m",
    max_animation_frames: int | None = 180,
    animation_loop_count: int = 0,
    animation_time_budget_seconds: float | None = None,
    share_y: list[int] | None = None,
) -> None:
    """Render static PNG or animated GIF graphs with one to eight stacked subplots.

    ``x_values`` may be a flat list (shared x-axis for all subplots) or a list
    of lists (one x series per subplot). When per-subplot x series are given,
    the overall x-axis range is the union of all series so subplots stay
    aligned on a common time/numeric axis.
    """
    if not y_series:
        raise ValueError("At least one y series is required.")

    subplot_count = len(y_series)
    if subplot_count > 8:
        raise ValueError("Matplotlib renderer supports up to eight subplots.")

    if len(y_labels) != subplot_count:
        raise ValueError("Each y series must provide a matching y-axis label.")
    if len(subplot_types) != subplot_count:
        raise ValueError("Each subplot must provide a graph type.")
    if len(subplot_colors) != subplot_count:
        raise ValueError("Each subplot must provide a graph color.")
    if len(inverted_bars) != subplot_count:
        raise ValueError("Each subplot must provide an inverted bar flag.")

    per_subplot_x = _normalize_x_series(x_values, subplot_count)
    for idx, x_arr in enumerate(per_subplot_x):
        if len(x_arr) != len(y_series[idx]):
            raise ValueError(f"x and y series lengths must match for subplot {idx + 1}.")

    # Normalize per-subplot "share Y range with subplot N" references.
    # Sharing is symmetric: both subplots in a pair use the union of their data.
    share_y_partner: list[int | None] = [None] * subplot_count
    for idx, target in enumerate(share_y or []):
        if target in (None, "", -1, 0):
            continue
        try:
            target_idx = int(target) - 1
        except (TypeError, ValueError):
            raise ValueError(f"shareY value for subplot {idx + 1} must be a subplot number.")
        if target_idx < 0 or target_idx >= subplot_count or target_idx == idx:
            raise ValueError(
                f"shareY for subplot {idx + 1} must reference another subplot (1-{subplot_count})."
            )
        share_y_partner[idx] = target_idx
        share_y_partner[target_idx] = idx

    def compute_y_limits_for(idx: int) -> tuple[float, float]:
        """Y limits for a subplot, widened to include its share-Y partner's data."""
        values = _finite_values(y_series[idx])
        partner = share_y_partner[idx]
        if partner is not None:
            values = values + _finite_values(y_series[partner])
        return _compute_y_limits(values)

    size_to_base = {
        "s": (7.0, 2.8),
        "m": (9.6, 3.2),
        "l": (12.8, 3.8),
    }
    fig_width, per_subplot_height = size_to_base.get(size, size_to_base["m"])
    # Keep tall multi-subplot figures at a manageable overall height.
    if subplot_count > 4:
        per_subplot_height *= 0.7
    fig_height = max(2.8, per_subplot_height * subplot_count)
    render_dpi = 120
    fig, axes = plt.subplots(
        subplot_count,
        1,
        sharex=True,
        figsize=(fig_width, fig_height),
        dpi=render_dpi,
    )
    if subplot_count == 1:
        axes = [axes]

    for idx, axis in enumerate(axes):
        axis.grid(alpha=0.25)
        axis.set_ylabel(y_labels[idx])
    axes[-1].set_xlabel("")

    for idx, subplot_type in enumerate(subplot_types):
        if subplot_type not in {"line", "scatter", "bar"}:
            raise ValueError("subplot types must be one of: line, scatter, bar")

    # Detect datetime mode when any per-subplot x series carries datetimes.
    x_is_datetime = any(
        series and isinstance(series[0], datetime) for series in per_subplot_x
    )
    datetime_rotation = None
    # Per-subplot plot x arrays (date numbers for datetimes, raw values otherwise).
    plot_x_series: list[list] = [list(series) for series in per_subplot_x]
    if x_is_datetime and mdates is not None:
        all_datetimes = [
            value
            for series in per_subplot_x
            for value in series
            if isinstance(value, datetime)
        ]
        span_seconds = (max(all_datetimes) - min(all_datetimes)).total_seconds() if len(all_datetimes) >= 2 else 0
        datetime_rotation = 50 if span_seconds < 86400 else 0
        # Keep real time spacing on the x-axis by converting datetimes to Matplotlib
        # date numbers; numeric series pass through unchanged.
        plot_x_series = [
            [float(value) for value in mdates.date2num(series)]
            if series and isinstance(series[0], datetime)
            else [float(value) for value in series]
            for series in per_subplot_x
        ]
        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        for axis in axes:
            axis.xaxis.set_major_locator(locator)
            axis.xaxis.set_major_formatter(formatter)
    # Shared x-axis range is the union of all per-subplot x values so subplots
    # stay aligned even when each uses its own timestamp column.
    all_plot_x = [value for series in plot_x_series for value in series]

    def apply_datetime_tick_rotation() -> None:
        """Rotate dense datetime labels without using autofmt_xdate recursion-prone path."""
        if datetime_rotation is None:
            return
        for label in axes[-1].get_xticklabels():
            label.set_rotation(datetime_rotation)
            label.set_horizontalalignment("right" if datetime_rotation else "center")

    def apply_layout() -> None:
        """Prefer tight layout, but keep a stable fallback for problematic backends."""
        try:
            fig.tight_layout(pad=1.0)
        except Exception:
            fig.subplots_adjust(left=0.1, right=0.98, top=0.96, bottom=0.14, hspace=0.28)
            if x_is_datetime and mdates is not None and datetime_rotation is not None:
                fig.subplots_adjust(bottom=0.28 if datetime_rotation else 0.16)
        # Right-align y-axis labels across stacked subplots so they line up
        # vertically regardless of label length.
        try:
            fig.align_ylabels()
        except Exception:
            pass

    # Per-subplot bar widths (each subplot uses its own x spacing).
    bar_widths_per_subplot: list[list[float]] = []
    for idx in range(subplot_count):
        widths = _compute_bar_widths(plot_x_series[idx])
        widths = _enforce_min_visible_bar_widths(all_plot_x, widths, fig_width, render_dpi)
        bar_widths_per_subplot.append(widths)

    def apply_x_limits() -> None:
        """Apply shared x-axis limits (union of all subplots) with edge padding."""
        x_numeric = _coerce_x_numeric(all_plot_x)
        if not x_numeric:
            return
        x_min, x_max = min(x_numeric), max(x_numeric)
        if math.isclose(x_min, x_max):
            x_min -= 1
            x_max += 1
        elif x_is_datetime and mdates is not None:
            # Date numbers use days as units; +/- 1.0 adds one full day padding.
            x_min -= 1.0
            x_max += 1.0
        for axis in axes:
            axis.set_xlim(x_min, x_max)

    def build_frame_end_fractions(frame_cap: int | None) -> list[float]:
        """Build animation frame endpoints as 0..1 progress fractions.

        Fractions keep subplots with different point counts in sync: each
        subplot reveals points up to ``fraction * len(series)``.
        """
        max_len = max((len(series) for series in y_series), default=0)
        if max_len == 0:
            return [1.0]
        if frame_cap is None or frame_cap <= 0:
            frame_cap = max_len
        frame_cap = max(1, min(int(frame_cap), max_len))
        if frame_cap == 1:
            fraction_set = {1.0}
        else:
            step = max(1, max_len // frame_cap)
            fraction_set = {min(1.0, (idx + 1) / max_len) for idx in range(0, max_len, step)}
            fraction_set.add(1.0)

        # Keep extrema frames so animated charts always show min/max values.
        for series in y_series:
            if not series:
                continue
            max_index = max(range(len(series)), key=series.__getitem__)
            min_index = min(range(len(series)), key=series.__getitem__)
            fraction_set.add((max_index + 1) / len(series))
            fraction_set.add((min_index + 1) / len(series))

        return sorted(fraction_set)

    def reset_artists() -> None:
        for idx, artist, artist_type in line_like:
            if artist_type == "line":
                artist.set_data([], [])
            else:
                # Scatter expects an (N, 2) shaped offsets array; [] can become 1-D and crash.
                artist.set_offsets([(float("nan"), float("nan"))])

        for bars in bar_containers:
            if bars is None:
                continue
            for patch in bars.patches:
                patch.set_height(0)

    frame_end_fractions = build_frame_end_fractions(max_animation_frames)

    if not animate:
        for idx, axis in enumerate(axes):
            color = subplot_colors[idx]
            if subplot_types[idx] == "line":
                axis.plot(plot_x_series[idx], y_series[idx], color=color, linewidth=2.2)
            elif subplot_types[idx] == "scatter":
                axis.scatter(plot_x_series[idx], y_series[idx], facecolors="none", edgecolors=color, linewidths=1.5, s=30)
            else:
                axis.bar(plot_x_series[idx], y_series[idx], color=color, width=bar_widths_per_subplot[idx])

            y_min, y_max = compute_y_limits_for(idx)
            axis.set_ylim(y_min, y_max)
            if inverted_bars[idx]:
                axis.invert_yaxis()

        apply_x_limits()
        if x_is_datetime and mdates is not None and datetime_rotation is not None:
            apply_datetime_tick_rotation()
        apply_layout()
        fig.savefig(output_path)
        plt.close(fig)
        return

    artists: list[Any] = []
    line_like = []
    bar_containers = []
    for idx, axis in enumerate(axes):
        color = subplot_colors[idx]
        subplot_type = subplot_types[idx]
        if subplot_type == "line":
            line, = axis.plot([], [], color=color, linewidth=2.2)
            line_like.append((idx, line, "line"))
            artists.append(line)
            bar_containers.append(None)
        elif subplot_type == "scatter":
            scatter = axis.scatter([], [], facecolors="none", edgecolors=color, linewidths=1.5, s=30)
            line_like.append((idx, scatter, "scatter"))
            artists.append(scatter)
            bar_containers.append(None)
        else:
            bars = axis.bar(plot_x_series[idx], [0.0] * len(plot_x_series[idx]), color=color, width=bar_widths_per_subplot[idx])
            bar_containers.append(bars)
            artists.extend(list(bars.patches))

    apply_x_limits()

    for idx, axis in enumerate(axes):
        y_min, y_max = compute_y_limits_for(idx)
        axis.set_ylim(y_min, y_max)
        if inverted_bars[idx]:
            axis.invert_yaxis()

    revealed_bar_indexes = [-1 for _ in bar_containers]

    def update(fraction: float) -> None:
        """Reveal each subplot's data up to the frame's progress fraction.

        Using a 0..1 fraction keeps subplots with different point counts in
        sync on the shared x-axis.
        """
        for idx, artist, artist_type in line_like:
            series_len = len(y_series[idx])
            upto = max(1, min(series_len, int(round(fraction * series_len))))
            x_slice = plot_x_series[idx][:upto]
            y_slice = y_series[idx][:upto]
            if artist_type == "line":
                artist.set_data(x_slice, y_slice)
            else:
                artist.set_offsets(list(zip(x_slice, y_slice, strict=False)))

        for idx, bars in enumerate(bar_containers):
            if bars is None:
                continue
            y_values = y_series[idx]
            series_len = len(y_values)
            end_index = max(0, min(series_len - 1, int(round(fraction * series_len)) - 1))
            start_index = revealed_bar_indexes[idx] + 1
            if start_index > end_index:
                start_index = 0
                for patch in bars.patches:
                    patch.set_height(0)

            for patch_idx in range(start_index, min(end_index, len(bars.patches) - 1) + 1):
                bars.patches[patch_idx].set_height(y_values[patch_idx])
            revealed_bar_indexes[idx] = max(revealed_bar_indexes[idx], end_index)

    reset_artists()

    if animation_time_budget_seconds is not None and animation_time_budget_seconds > 0 and len(frame_end_fractions) > 1:
        probe_count = min(3, len(frame_end_fractions))
        probe_start = perf_counter()
        for probe_frame_idx in range(len(frame_end_fractions) - probe_count, len(frame_end_fractions)):
            update(frame_end_fractions[probe_frame_idx])
            fig.canvas.draw()
        probe_elapsed = perf_counter() - probe_start
        average_frame_seconds = probe_elapsed / probe_count if probe_count else 0.0
        reset_artists()

        if average_frame_seconds > 0:
            budget_adjusted_cap = int(animation_time_budget_seconds / (average_frame_seconds * 1.2))
            budget_adjusted_cap = max(probe_count, budget_adjusted_cap)
            if budget_adjusted_cap < len(frame_end_fractions):
                frame_end_fractions = build_frame_end_fractions(budget_adjusted_cap)
                reset_artists()

    if x_is_datetime and mdates is not None and datetime_rotation is not None:
        apply_datetime_tick_rotation()
    apply_layout()
    frame_count = max(len(frame_end_fractions), 1)
    seconds_per_frame = 0.1
    target_loop_seconds = frame_count * seconds_per_frame
    if target_loop_seconds < 5.0:
        seconds_per_frame = 5.0 / frame_count
    elif target_loop_seconds > 10.0:
        seconds_per_frame = 10.0 / frame_count
    frame_duration_ms = max(20, int(seconds_per_frame * 1000))
    frames: list[Image.Image] = []
    for fraction in frame_end_fractions:
        update(fraction)
        fig.canvas.draw()
        width, height = fig.canvas.get_width_height()
        buffer = fig.canvas.buffer_rgba()
        frame = Image.frombuffer("RGBA", (width, height), buffer, "raw", "RGBA", 0, 1).convert("P")
        frames.append(frame.copy())

    if not frames:
        raise ValueError("Animated subplot render produced no frames.")

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=max(0, int(animation_loop_count)),
        optimize=False,
    )
    plt.close(fig)

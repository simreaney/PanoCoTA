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
    """Convert x values to numeric positions for axis bounds."""
    if not x_values:
        return []

    try:
        return [float(value.timestamp()) for value in x_values]
    except Exception:
        pass

    try:
        return [float(value) for value in x_values]
    except Exception:
        return [float(i) for i in range(len(x_values))]


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


def _compute_y_limits(y_values: list[float]) -> tuple[float, float]:
    """Compute y-axis limits with +/-10% padding and a zero floor for non-negative data."""
    if not y_values:
        return (-1.0, 1.0)

    min_value = min(y_values)
    max_value = max(y_values)

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
) -> None:
    """Render static PNG or animated GIF graphs with one to three stacked subplots."""
    if not y_series:
        raise ValueError("At least one y series is required.")

    subplot_count = len(y_series)
    if subplot_count > 3:
        raise ValueError("Matplotlib renderer supports up to three subplots.")

    if len(y_labels) != subplot_count:
        raise ValueError("Each y series must provide a matching y-axis label.")
    if len(subplot_types) != subplot_count:
        raise ValueError("Each subplot must provide a graph type.")
    if len(subplot_colors) != subplot_count:
        raise ValueError("Each subplot must provide a graph color.")
    if len(inverted_bars) != subplot_count:
        raise ValueError("Each subplot must provide an inverted bar flag.")

    for values in y_series:
        if len(values) != len(x_values):
            raise ValueError("x and y series lengths must match for subplot rendering.")

    size_to_base = {
        "s": (7.0, 2.8),
        "m": (9.6, 3.2),
        "l": (12.8, 3.8),
    }
    fig_width, per_subplot_height = size_to_base.get(size, size_to_base["m"])
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

    x_is_datetime = bool(x_values) and isinstance(x_values[0], datetime)
    datetime_rotation = None
    plot_x_values = x_values
    if x_is_datetime and mdates is not None:
        span_seconds = (max(x_values) - min(x_values)).total_seconds() if len(x_values) >= 2 else 0
        datetime_rotation = 50 if span_seconds < 86400 else 0
        # Keep real time spacing on the x-axis by converting datetimes to Matplotlib date numbers.
        plot_x_values = [float(value) for value in mdates.date2num(x_values)]
        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        for axis in axes:
            axis.xaxis.set_major_locator(locator)
            axis.xaxis.set_major_formatter(formatter)

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

    bar_widths = _compute_bar_widths(plot_x_values)
    bar_widths = _enforce_min_visible_bar_widths(plot_x_values, bar_widths, fig_width, render_dpi)

    def build_frame_end_indexes(frame_cap: int | None) -> list[int]:
        if frame_cap is None or frame_cap <= 0:
            frame_cap = len(plot_x_values)
        frame_cap = max(1, min(int(frame_cap), len(plot_x_values)))
        if frame_cap == 1:
            frame_index_set = {len(plot_x_values) - 1}
        else:
            step = max(1, len(plot_x_values) // frame_cap)
            frame_index_set = set(range(0, len(plot_x_values), step))
            frame_index_set.add(len(plot_x_values) - 1)

        # Keep extrema frames so animated charts always show min/max values used for axis limits.
        for series in y_series:
            if not series:
                continue
            max_index = max(range(len(series)), key=series.__getitem__)
            min_index = min(range(len(series)), key=series.__getitem__)
            frame_index_set.add(max_index)
            frame_index_set.add(min_index)

        return sorted(frame_index_set)

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

    frame_end_indexes = build_frame_end_indexes(max_animation_frames)

    if not animate:
        for idx, axis in enumerate(axes):
            color = subplot_colors[idx]
            if subplot_types[idx] == "line":
                axis.plot(plot_x_values, y_series[idx], color=color, linewidth=2.2)
            elif subplot_types[idx] == "scatter":
                axis.scatter(plot_x_values, y_series[idx], color=color, s=24)
            else:
                axis.bar(plot_x_values, y_series[idx], color=color, width=bar_widths)

            y_values = y_series[idx]
            y_min, y_max = _compute_y_limits(y_values)
            axis.set_ylim(y_min, y_max)
            if inverted_bars[idx]:
                axis.invert_yaxis()

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
            scatter = axis.scatter([], [], color=color, s=24)
            line_like.append((idx, scatter, "scatter"))
            artists.append(scatter)
            bar_containers.append(None)
        else:
            bars = axis.bar(plot_x_values, [0.0] * len(plot_x_values), color=color, width=bar_widths)
            bar_containers.append(bars)
            artists.extend(list(bars.patches))

    x_numeric = _coerce_x_numeric(plot_x_values)
    x_min, x_max = min(x_numeric), max(x_numeric)
    if math.isclose(x_min, x_max):
        x_min -= 1
        x_max += 1
    for axis in axes:
        axis.set_xlim(x_min, x_max)

    for idx, axis in enumerate(axes):
        y_values = y_series[idx]
        y_min, y_max = _compute_y_limits(y_values)
        axis.set_ylim(y_min, y_max)
        if inverted_bars[idx]:
            axis.invert_yaxis()

    revealed_bar_indexes = [-1 for _ in bar_containers]

    def update(frame_idx: int, current_frame_end_indexes: list[int]) -> None:
        """Append full-series data points up to the frame's endpoint index."""
        end_index = current_frame_end_indexes[frame_idx]
        upto = end_index + 1

        for idx, artist, artist_type in line_like:
            x_slice = plot_x_values[:upto]
            y_slice = y_series[idx][:upto]
            if artist_type == "line":
                artist.set_data(x_slice, y_slice)
            else:
                artist.set_offsets(list(zip(x_slice, y_slice, strict=False)))

        for idx, bars in enumerate(bar_containers):
            if bars is None:
                continue
            y_values = y_series[idx]
            start_index = revealed_bar_indexes[idx] + 1
            if start_index > end_index:
                start_index = 0
                for patch in bars.patches:
                    patch.set_height(0)

            for patch_idx in range(start_index, min(end_index, len(bars.patches) - 1) + 1):
                bars.patches[patch_idx].set_height(y_values[patch_idx])
            revealed_bar_indexes[idx] = max(revealed_bar_indexes[idx], end_index)

    reset_artists()

    if animation_time_budget_seconds is not None and animation_time_budget_seconds > 0 and len(frame_end_indexes) > 1:
        probe_count = min(3, len(frame_end_indexes))
        probe_indexes = frame_end_indexes[-probe_count:]
        probe_start = perf_counter()
        for probe_frame_idx in range(len(frame_end_indexes) - probe_count, len(frame_end_indexes)):
            update(probe_frame_idx, frame_end_indexes)
            fig.canvas.draw()
        probe_elapsed = perf_counter() - probe_start
        average_frame_seconds = probe_elapsed / probe_count if probe_count else 0.0
        reset_artists()

        if average_frame_seconds > 0:
            budget_adjusted_cap = int(animation_time_budget_seconds / (average_frame_seconds * 1.2))
            budget_adjusted_cap = max(probe_count, budget_adjusted_cap)
            if budget_adjusted_cap < len(frame_end_indexes):
                frame_end_indexes = build_frame_end_indexes(budget_adjusted_cap)
                reset_artists()

    if x_is_datetime and mdates is not None and datetime_rotation is not None:
        apply_datetime_tick_rotation()
    apply_layout()
    frame_count = max(len(frame_end_indexes), 1)
    seconds_per_frame = 0.1
    target_loop_seconds = frame_count * seconds_per_frame
    if target_loop_seconds < 5.0:
        seconds_per_frame = 5.0 / frame_count
    elif target_loop_seconds > 10.0:
        seconds_per_frame = 10.0 / frame_count
    frame_duration_ms = max(20, int(seconds_per_frame * 1000))
    frames: list[Image.Image] = []
    for frame_idx in range(len(frame_end_indexes)):
        update(frame_idx, frame_end_indexes)
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

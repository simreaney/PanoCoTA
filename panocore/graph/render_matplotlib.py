"""Matplotlib graph renderer."""

from __future__ import annotations

import math
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
    fig, axes = plt.subplots(
        subplot_count,
        1,
        sharex=True,
        figsize=(fig_width, fig_height),
        dpi=120,
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

    if not animate:
        for idx, axis in enumerate(axes):
            color = subplot_colors[idx]
            if subplot_types[idx] == "line":
                axis.plot(plot_x_values, y_series[idx], color=color, linewidth=2.2)
            elif subplot_types[idx] == "scatter":
                axis.scatter(plot_x_values, y_series[idx], color=color, s=24)
            else:
                axis.bar(plot_x_values, y_series[idx], color=color, alpha=0.88, width=bar_widths)

            y_values = y_series[idx]
            y_padding = (max(y_values) - min(y_values)) * 0.1 or 1
            axis.set_ylim(min(y_values) - y_padding, max(y_values) + y_padding)
            if inverted_bars[idx]:
                axis.invert_yaxis()

        if x_is_datetime and mdates is not None and datetime_rotation is not None:
            apply_datetime_tick_rotation()
        apply_layout()
        fig.savefig(output_path)
        plt.close(fig)
        return

    max_frames = 180
    step = max(1, len(x_values) // max_frames)
    frame_indexes = list(range(0, len(x_values), step))
    if frame_indexes[-1] != len(x_values) - 1:
        frame_indexes.append(len(x_values) - 1)

    x_anim = [plot_x_values[idx] for idx in frame_indexes]
    y_anim_series = [[series[idx] for idx in frame_indexes] for series in y_series]
    bar_widths_anim = [bar_widths[idx] for idx in frame_indexes]

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
            bars = axis.bar(x_anim, [0.0] * len(x_anim), color=color, alpha=0.88, width=bar_widths_anim)
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
        y_padding = (max(y_values) - min(y_values)) * 0.1 or 1
        axis.set_ylim(min(y_values) - y_padding, max(y_values) + y_padding)
        if inverted_bars[idx]:
            axis.invert_yaxis()

    def update(frame_idx: int) -> None:
        """Append data points up to the current animation frame."""
        upto = frame_idx + 1

        for idx, artist, artist_type in line_like:
            x_slice = x_anim[:upto]
            y_slice = y_anim_series[idx][:upto]
            if artist_type == "line":
                artist.set_data(x_slice, y_slice)
            else:
                artist.set_offsets(list(zip(x_slice, y_slice, strict=False)))

        for idx, bars in enumerate(bar_containers):
            if bars is None:
                continue
            y_slice = y_anim_series[idx][:upto]
            for patch_idx, patch in enumerate(bars.patches):
                patch.set_height(y_slice[patch_idx] if patch_idx < len(y_slice) else 0)

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

    if x_is_datetime and mdates is not None and datetime_rotation is not None:
        apply_datetime_tick_rotation()
    apply_layout()
    frame_duration_ms = max(20, int(80 / max(animation_speed, 0.25)))
    frames: list[Image.Image] = []
    for frame_idx in range(len(x_anim)):
        update(frame_idx)
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
        loop=0,
        optimize=False,
    )
    plt.close(fig)

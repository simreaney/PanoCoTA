"""Common graph helpers shared across renderers."""

from __future__ import annotations

import math
from datetime import datetime


def coerce_x_numeric(x_values: list) -> list[float]:
    """Convert x values (datetime/numeric/text) to numeric positions."""
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


def build_x_ticks(x_values: list, points: list[tuple[float, float]], x_is_datetime: bool) -> list[tuple[float, str]]:
    """Return evenly spaced tick labels for x-axis rendering."""
    if not points:
        return []

    tick_count = min(5, len(points))
    if tick_count <= 1:
        indices = [0]
    else:
        indices = [round(i * (len(points) - 1) / (tick_count - 1)) for i in range(tick_count)]

    datetime_label_format = "%Y-%m-%d"
    if x_is_datetime:
        dt_values = [value for value in x_values if isinstance(value, datetime)]
        if len(dt_values) >= 2:
            span = max(dt_values) - min(dt_values)
            if span.total_seconds() < 86400:
                datetime_label_format = "%Y-%m-%d %H:%M"

    ticks: list[tuple[float, str]] = []
    for idx in indices:
        x_pos = points[idx][0]
        if x_is_datetime and isinstance(x_values[idx], datetime):
            label = x_values[idx].strftime(datetime_label_format)
        else:
            value = x_values[idx]
            label = f"{value:.2f}" if isinstance(value, float) else str(value)
        ticks.append((x_pos, label))
    return ticks


def scale_points_for_canvas(
    x_values: list,
    y_values: list[float],
    width: int,
    height: int,
    left_pad: int,
    right_pad: int,
    top_pad: int,
    bottom_pad: int,
    invert_y: bool = False,
) -> tuple[list[tuple[float, float]], float, float]:
    """Map x/y series into plot coordinates for Pillow drawing."""
    x_numeric = coerce_x_numeric(x_values)
    x_min = min(x_numeric)
    x_max = max(x_numeric)
    x_range = x_max - x_min if not math.isclose(x_min, x_max) else 1.0

    y_min = min(y_values)
    y_max = max(y_values)
    if math.isclose(y_min, y_max):
        y_min -= 1
        y_max += 1

    points: list[tuple[float, float]] = []
    for i, y_val in enumerate(y_values):
        x_norm = (x_numeric[i] - x_min) / x_range
        x = left_pad + (x_norm * (width - (left_pad + right_pad)))
        y_norm = (y_val - y_min) / (y_max - y_min)
        if invert_y:
            y = top_pad + (y_norm * (height - (top_pad + bottom_pad)))
        else:
            y = (height - bottom_pad) - (y_norm * (height - (top_pad + bottom_pad)))
        points.append((x, y))

    return points, y_min, y_max

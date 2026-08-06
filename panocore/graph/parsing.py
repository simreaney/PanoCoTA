"""CSV parsing and axis-label helpers for graph generation."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path


def derive_y_axis_label(y_col: str, y_label: str | None, y_unit: str | None) -> str:
    """Return explicit or inferred y-axis label with optional unit."""
    explicit_label = (y_label or "").strip()
    explicit_unit = (y_unit or "").strip()
    if explicit_label:
        return f"{explicit_label} ({explicit_unit})" if explicit_unit else explicit_label

    match = re.search(r"^(.+?)[_\s]*[\[(]([^\])]+)[\])]$", y_col)
    if match:
        base = match.group(1).strip(" _-")
        unit = match.group(2).strip()
        if base and unit:
            return f"{base} ({unit})"

    if "_" in y_col:
        parts = [p for p in y_col.split("_") if p]
        if len(parts) >= 2 and len(parts[-1]) <= 5:
            return f"{' '.join(parts[:-1])} ({parts[-1]})"

    return y_col


def load_csv_rows(csv_path: Path) -> tuple[list[str], list[dict]]:
    """Load CSV rows and field names from disk."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []

    if not rows:
        raise ValueError("CSV file has no data rows.")
    return fields, rows


def parse_datetime_value(text: str) -> datetime:
    """Parse text into datetime across common CSV timestamp formats."""
    normalized = text.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    common_formats = (
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
    )
    for fmt in common_formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    raise ValueError("not datetime")


def extract_series(
    fields: list[str],
    rows: list[dict],
    x_col: str,
    y_col: str,
) -> tuple[list, list[float], str, bool]:
    """Extract x/y arrays from CSV rows and detect datetime x-axis mode."""
    if y_col not in fields:
        raise ValueError(f"Column '{y_col}' not found in CSV.")
    if x_col and x_col not in fields:
        raise ValueError(f"Column '{x_col}' not found in CSV.")

    x_raw: list = []
    y_values: list[float] = []
    for idx, row in enumerate(rows):
        y_text = str(row.get(y_col, "")).strip()
        try:
            y_val = float(y_text)
        except ValueError:
            continue

        if x_col:
            x_text = str(row.get(x_col, "")).strip()
            x_raw.append(x_text if x_text else str(idx))
        else:
            x_raw.append(idx)
        y_values.append(y_val)

    if not y_values:
        raise ValueError("No numeric data found in y column after parsing.")

    if not x_col:
        return [float(i) for i in range(len(y_values))], y_values, "index", False

    x_dt: list[datetime] = []
    dt_ok = True
    for value in x_raw:
        try:
            x_dt.append(parse_datetime_value(str(value)))
        except ValueError:
            dt_ok = False
            break
    if dt_ok:
        return x_dt, y_values, x_col, True

    x_num: list[float] = []
    num_ok = True
    for value in x_raw:
        try:
            x_num.append(float(value))
        except ValueError:
            num_ok = False
            break
    if num_ok:
        return x_num, y_values, x_col, False

    return [float(i) for i in range(len(y_values))], y_values, x_col, False


def extract_multi_series(
    fields: list[str],
    rows: list[dict],
    x_col: str,
    y_cols: list[str],
) -> tuple[list, list[list[float]], str, bool]:
    """Extract one shared x-array and multiple y series from CSV rows."""
    if not y_cols:
        raise ValueError("At least one y column is required.")

    for y_col in y_cols:
        if y_col not in fields:
            raise ValueError(f"Column '{y_col}' not found in CSV.")
    if x_col and x_col not in fields:
        raise ValueError(f"Column '{x_col}' not found in CSV.")

    x_raw: list = []
    y_series = [[] for _ in y_cols]
    kept_rows = 0

    for idx, row in enumerate(rows):
        parsed_values: list[float] = []
        row_valid = True
        for y_col in y_cols:
            y_text = str(row.get(y_col, "")).strip()
            try:
                parsed_values.append(float(y_text))
            except ValueError:
                row_valid = False
                break

        if not row_valid:
            continue

        if x_col:
            x_text = str(row.get(x_col, "")).strip()
            x_raw.append(x_text if x_text else str(kept_rows))
        else:
            x_raw.append(kept_rows)

        for series_idx, value in enumerate(parsed_values):
            y_series[series_idx].append(value)
        kept_rows += 1

    if kept_rows == 0:
        raise ValueError("No numeric data found across selected y columns after parsing.")

    if not x_col:
        return [float(i) for i in range(kept_rows)], y_series, "index", False

    x_dt: list[datetime] = []
    dt_ok = True
    for value in x_raw:
        try:
            x_dt.append(parse_datetime_value(str(value)))
        except ValueError:
            dt_ok = False
            break
    if dt_ok:
        return x_dt, y_series, x_col, True

    x_num: list[float] = []
    num_ok = True
    for value in x_raw:
        try:
            x_num.append(float(value))
        except ValueError:
            num_ok = False
            break
    if num_ok:
        return x_num, y_series, x_col, False

    return [float(i) for i in range(kept_rows)], y_series, x_col, False

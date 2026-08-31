"""CSV parsing and axis-label helpers for graph generation."""

from __future__ import annotations

import csv
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def parse_finite_float(text: str) -> float | None:
    """Parse text as a finite float; return None for empty/nan/inf values."""
    value = str(text or "").strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


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
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

    common_formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S.%f",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S.%f",
        "%Y%m%d",
        "%d%m%Y",
    )
    for fmt in common_formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
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
        y_val = parse_finite_float(row.get(y_col, ""))
        if y_val is None:
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
        parsed = parse_finite_float(value)
        if parsed is None:
            num_ok = False
            break
        x_num.append(parsed)
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
            y_val = parse_finite_float(row.get(y_col, ""))
            if y_val is None:
                row_valid = False
                break
            parsed_values.append(y_val)

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
        parsed = parse_finite_float(value)
        if parsed is None:
            num_ok = False
            break
        x_num.append(parsed)
    if num_ok:
        return x_num, y_series, x_col, False

    return [float(i) for i in range(kept_rows)], y_series, x_col, False


def extract_multi_series_with_x_cols(
    fields: list[str],
    rows: list[dict],
    x_col: str,
    y_cols: list[str],
    x_cols: list[str],
) -> tuple[list[list], list[list[float]], bool]:
    """Extract per-subplot x arrays and y series, each subplot using its own x column.

    Falls back to the shared ``x_col`` (or row index) when a subplot has no
    dedicated x column. Returns (x_series, y_series, x_is_datetime) where
    x_series[i] is the x array for subplot i.
    """
    if not y_cols:
        raise ValueError("At least one y column is required.")

    for y_col in y_cols:
        if y_col not in fields:
            raise ValueError(f"Column '{y_col}' not found in CSV.")
    if x_col and x_col not in fields:
        raise ValueError(f"Column '{x_col}' not found in CSV.")
    for x_candidate in x_cols:
        if x_candidate and x_candidate not in fields:
            raise ValueError(f"Column '{x_candidate}' not found in CSV.")

    effective_x_cols = [
        (x_cols[idx] if idx < len(x_cols) else "").strip() or x_col
        for idx in range(len(y_cols))
    ]

    # Parse each series independently so datasets with different row counts
    # (or gaps) do not truncate one another: a row is kept for a series when
    # that series' y value is numeric, paired with the x value from the same row.
    x_raw_series: list[list] = [[] for _ in y_cols]
    y_series = [[] for _ in y_cols]
    for series_idx, y_col in enumerate(y_cols):
        x_candidate = effective_x_cols[series_idx]
        kept = 0
        for row in rows:
            y_val = parse_finite_float(row.get(y_col, ""))
            if y_val is None:
                continue
            y_series[series_idx].append(y_val)
            if x_candidate:
                x_text = str(row.get(x_candidate, "")).strip()
                x_raw_series[series_idx].append(x_text if x_text else kept)
            else:
                x_raw_series[series_idx].append(kept)
            kept += 1

    if not any(y_series):
        raise ValueError("No numeric data found across selected y columns after parsing.")

    x_series: list[list] = []
    for series_idx, x_raw in enumerate(x_raw_series):
        if not effective_x_cols[series_idx]:
            x_series.append([float(i) for i in range(len(x_raw))])
            continue

        x_dt: list[datetime] = []
        dt_ok = True
        for value in x_raw:
            try:
                x_dt.append(parse_datetime_value(str(value)))
            except ValueError:
                dt_ok = False
                break
        if dt_ok:
            x_series.append(x_dt)
            continue

        x_num: list[float] = []
        num_ok = True
        for value in x_raw:
            parsed = parse_finite_float(value)
            if parsed is None:
                num_ok = False
                break
            x_num.append(parsed)
        if num_ok:
            x_series.append(x_num)
            continue

        x_series.append([float(i) for i in range(len(x_raw))])

    # Datetime axis mode when any series carries datetime x values.
    x_is_datetime = any(
        series and isinstance(series[0], datetime) for series in x_series
    )

    # Guard against an incompatible mix: a subplot using auto-index (no x
    # column) alongside a subplot using a datetime x column. Their scales
    # (row numbers vs. date numbers) differ by orders of magnitude, so the
    # shared axis would squash one series into an invisible sliver.
    if x_is_datetime:
        for series_idx, series in enumerate(x_series):
            if not effective_x_cols[series_idx] and series:
                raise ValueError(
                    "A subplot uses the auto index X while another subplot uses a "
                    "datetime X column. Set the shared X Column to a real timestamp "
                    "column (or give every subplot its own X Column) so all subplots "
                    "share a comparable axis."
                )

    return x_series, y_series, x_is_datetime

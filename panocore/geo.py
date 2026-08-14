"""EXIF GPS extraction helpers for panorama images."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PIL.ExifTags import IFD

# EXIF GPS IFD tag ids (see EXIF 2.3 spec, section 4.6.6).
_GPS_LATITUDE_REF = 1
_GPS_LATITUDE = 2
_GPS_LONGITUDE_REF = 3
_GPS_LONGITUDE = 4
_GPS_IMG_DIRECTION = 17


def _rational_to_float(value) -> float | None:
    """Convert an EXIF rational to a float, rejecting NaN/inf.

    Some cameras write a GPS IFD with all-zero (0/0 => NaN) rationals when GPS
    was enabled but never acquired a fix; treat that the same as no GPS data.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _dms_to_decimal(dms, ref: str | None) -> float | None:
    if not dms or len(dms) != 3:
        return None
    parts = [_rational_to_float(part) for part in dms]
    if any(part is None for part in parts):
        return None
    degrees, minutes, seconds = parts
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if str(ref or "").strip().upper() in {"S", "W"}:
        decimal = -decimal
    return decimal


def extract_gps(path: Path) -> dict | None:
    """Return {lat, lon, heading} decoded from an image's EXIF GPS tags, or None.

    `heading` is the compass direction (degrees) the camera was facing when the
    photo was captured (EXIF GPSImgDirection), and may be None even when
    lat/lon are present since not all cameras record it.
    """
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            gps_ifd = exif.get_ifd(IFD.GPSInfo) if exif else None
    except Exception:
        return None

    if not gps_ifd:
        return None

    lat = _dms_to_decimal(gps_ifd.get(_GPS_LATITUDE), gps_ifd.get(_GPS_LATITUDE_REF))
    lon = _dms_to_decimal(gps_ifd.get(_GPS_LONGITUDE), gps_ifd.get(_GPS_LONGITUDE_REF))
    if lat is None or lon is None:
        return None

    heading = _rational_to_float(gps_ifd.get(_GPS_IMG_DIRECTION))
    if heading is not None:
        heading = heading % 360.0

    return {"lat": round(lat, 7), "lon": round(lon, 7), "heading": heading}

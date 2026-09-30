from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, Sequence

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


def mean_point(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon


def median_point(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    lats = sorted(p[0] for p in points)
    lons = sorted(p[1] for p in points)
    n = len(points)
    mid = n // 2
    if n % 2:
        return lats[mid], lons[mid]
    return (lats[mid - 1] + lats[mid]) / 2.0, (lons[mid - 1] + lons[mid]) / 2.0


def parse_confidence(value: str | float | int | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    mapping = {"l": 30.0, "low": 30.0, "n": 50.0, "nominal": 50.0, "h": 80.0, "high": 80.0}
    if text in mapping:
        return mapping[text]
    try:
        return float(text)
    except ValueError:
        return None


def day_night_norm(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().upper()
    if v in {"D", "DAY"}:
        return "D"
    if v in {"N", "NIGHT"}:
        return "N"
    return None


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def unique_days(times: Iterable[datetime]) -> int:
    return len({t.date() for t in times})

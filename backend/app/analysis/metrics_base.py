from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from typing import Iterable


def to_float(value, default: float | None = None) -> float | None:
    try:
        value = float(value)
        return value if isfinite(value) else default
    except (TypeError, ValueError):
        return default


def parse_date(value) -> date | None:
    if value is None:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def pct_return(first: float | None, last: float | None) -> float | None:
    first = to_float(first)
    last = to_float(last)
    if first is None or last is None or first <= 0:
        return None
    return (last / first) - 1


def clamp(value: float | None, min_value: float = 0.0, max_value: float = 100.0) -> float | None:
    if value is None:
        return None
    return max(min_value, min(max_value, float(value)))


def avg(values: Iterable[float | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None

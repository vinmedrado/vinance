from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

DEFAULT_START_DATE = "2015-01-01"


def today_iso() -> str:
    return date.today().isoformat()


def parse_date(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def next_day_iso(value: str | None, fallback: str = DEFAULT_START_DATE) -> str:
    parsed = parse_date(value)
    if not parsed:
        return fallback
    return (parsed + timedelta(days=1)).isoformat()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()

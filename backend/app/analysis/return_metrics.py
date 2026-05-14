from __future__ import annotations

from datetime import date
from .metrics_base import pct_return, parse_date


def _return_since_days(rows: list[dict], days: int) -> float | None:
    if not rows:
        return None
    last_date = parse_date(rows[-1]["date"])
    if not last_date:
        return None
    target_ord = last_date.toordinal() - days
    candidates = [r for r in rows if parse_date(r["date"]) and parse_date(r["date"]).toordinal() <= target_ord]
    base = candidates[-1] if candidates else rows[0]
    return pct_return(base.get("close"), rows[-1].get("close"))


def calculate_return_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {}
    last = rows[-1]
    last_date = parse_date(last["date"])
    ytd = None
    if last_date:
        first_year = next((r for r in rows if parse_date(r["date"]) and parse_date(r["date"]).year == last_date.year), None)
        if first_year:
            ytd = pct_return(first_year.get("close"), last.get("close"))
    return {
        "retorno_7d": _return_since_days(rows, 7),
        "retorno_30d": _return_since_days(rows, 30),
        "retorno_90d": _return_since_days(rows, 90),
        "retorno_180d": _return_since_days(rows, 180),
        "retorno_365d": _return_since_days(rows, 365),
        "retorno_ytd": ytd,
        "as_of_date": str(last_date) if last_date else None,
    }

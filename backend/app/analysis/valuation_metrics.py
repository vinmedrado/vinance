from __future__ import annotations

from datetime import timedelta
from .metrics_base import avg, parse_date


def _moving_average(rows: list[dict], window: int) -> float | None:
    closes = [float(r["close"]) for r in rows if r.get("close") is not None]
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def calculate_trend_metrics(rows: list[dict]) -> dict:
    last_close = float(rows[-1]["close"]) if rows and rows[-1].get("close") is not None else None
    ma20 = _moving_average(rows, 20)
    ma50 = _moving_average(rows, 50)
    ma200 = _moving_average(rows, 200)
    def dist(ma):
        return (last_close / ma - 1) if last_close and ma and ma > 0 else None
    return {
        "media_movel_20": ma20,
        "media_movel_50": ma50,
        "media_movel_200": ma200,
        "distancia_mm20": dist(ma20),
        "distancia_mm50": dist(ma50),
        "distancia_mm200": dist(ma200),
    }


def calculate_dividend_metrics(rows: list[dict], dividends: list[dict]) -> dict:
    if not rows:
        return {"dividend_yield_12m": None, "frequencia_dividendos": 0, "total_dividendos_12m": 0.0}
    last_date = parse_date(rows[-1]["date"])
    last_close = float(rows[-1]["close"]) if rows[-1].get("close") else None
    if not last_date:
        return {"dividend_yield_12m": None, "frequencia_dividendos": 0, "total_dividendos_12m": 0.0}
    cutoff = last_date - timedelta(days=365)
    valid = []
    for d in dividends:
        dt = parse_date(d.get("date"))
        amount = d.get("amount")
        if dt and dt >= cutoff and amount is not None:
            valid.append(float(amount))
    total = sum(valid)
    dy = total / last_close if last_close and last_close > 0 else None
    return {"dividend_yield_12m": dy, "frequencia_dividendos": len(valid), "total_dividendos_12m": total}

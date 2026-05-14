from __future__ import annotations

from .metrics_base import avg, parse_date


def calculate_liquidity_metrics(rows: list[dict]) -> dict:
    vols = [r.get("volume") for r in rows]
    volume_medio_30d = avg(vols[-30:])
    volume_medio_90d = avg(vols[-90:])
    dias_sem_negociacao = 0
    dates = [parse_date(r.get("date")) for r in rows]
    dates = [d for d in dates if d]
    if len(dates) >= 2:
        expected_span = (dates[-1] - dates[0]).days + 1
        dias_sem_negociacao = max(0, expected_span - len(set(dates)))
    base = volume_medio_90d or volume_medio_30d or 0
    if base >= 5_000_000:
        score = 100
    elif base >= 1_000_000:
        score = 80
    elif base >= 100_000:
        score = 55
    elif base > 0:
        score = 30
    else:
        score = 0
    return {
        "volume_medio_30d": volume_medio_30d,
        "volume_medio_90d": volume_medio_90d,
        "dias_sem_negociacao": dias_sem_negociacao,
        "liquidez_score": score,
    }

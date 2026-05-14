from __future__ import annotations

import math
from statistics import mean
from typing import Iterable


def clean_series(values: Iterable[float | int | None]) -> list[float]:
    result: list[float] = []
    for value in values or []:
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed) and parsed > 0:
            result.append(parsed)
    return result


def pct_return(prices: Iterable[float | int | None], periods: int | None = None) -> float | None:
    clean = clean_series(prices)
    if len(clean) < 2:
        return None
    start = clean[0] if periods is None or len(clean) <= periods else clean[-periods - 1]
    return (clean[-1] / start) - 1 if start > 0 else None


def daily_returns(prices: Iterable[float | int | None]) -> list[float]:
    clean = clean_series(prices)
    if len(clean) < 2:
        return []
    return [(clean[i] / clean[i - 1]) - 1 for i in range(1, len(clean)) if clean[i - 1] > 0]


def volatility(prices: Iterable[float | int | None], annualize: bool = True) -> float | None:
    returns = daily_returns(prices)
    if len(returns) < 2:
        return None
    avg = mean(returns)
    var = sum((r - avg) ** 2 for r in returns) / max(len(returns) - 1, 1)
    vol = math.sqrt(var)
    return vol * math.sqrt(252) if annualize else vol


def max_drawdown(prices: Iterable[float | int | None]) -> float | None:
    clean = clean_series(prices)
    if len(clean) < 2:
        return None
    peak = clean[0]
    worst = 0.0
    for price in clean:
        peak = max(peak, price)
        worst = min(worst, (price / peak) - 1)
    return worst


def normalize(value: float | None, min_value: float, max_value: float) -> float:
    if value is None or max_value == min_value:
        return 0.0
    return max(0.0, min(1.0, (float(value) - min_value) / (max_value - min_value)))


def safe_round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def correlation(series_a: Iterable[float | int | None], series_b: Iterable[float | int | None]) -> float | None:
    a = daily_returns(series_a)
    b = daily_returns(series_b)
    n = min(len(a), len(b))
    if n < 3:
        return None
    a = a[-n:]
    b = b[-n:]
    avg_a = mean(a)
    avg_b = mean(b)
    denom_a = math.sqrt(sum((x - avg_a) ** 2 for x in a))
    denom_b = math.sqrt(sum((y - avg_b) ** 2 for y in b))
    if denom_a == 0 or denom_b == 0:
        return None
    return sum((x - avg_a) * (y - avg_b) for x, y in zip(a, b)) / (denom_a * denom_b)

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, pstdev
from typing import Iterable


def to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_decimal(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def clean_series(values: Iterable) -> list[float]:
    return [v for v in (to_float(item) for item in values) if v is not None]


def calculate_momentum(values: Iterable, periods: int) -> Decimal | None:
    series = clean_series(values)
    if len(series) <= periods or series[-periods - 1] == 0:
        return None
    return to_decimal(((series[-1] / series[-periods - 1]) - 1) * 100)


def calculate_volatility(values: Iterable, periods: int) -> Decimal | None:
    series = clean_series(values)
    if len(series) <= periods:
        return None
    window = series[-periods - 1 :]
    returns: list[float] = []
    for previous, current in zip(window, window[1:]):
        if previous:
            returns.append((current / previous) - 1)
    if len(returns) < 2:
        return None
    return to_decimal(pstdev(returns) * (252 ** 0.5) * 100)


def calculate_zscore(value, peers: Iterable) -> Decimal | None:
    current = to_float(value)
    series = clean_series(peers)
    if current is None or len(series) < 2:
        return None
    deviation = pstdev(series)
    if deviation == 0:
        return Decimal("0.000000")
    return to_decimal((current - mean(series)) / deviation)


def calculate_trend(values: Iterable, periods: int = 3) -> Decimal | None:
    series = clean_series(values)
    if len(series) <= periods:
        return None
    return to_decimal(series[-1] - series[-periods - 1])


def calculate_relative_return(asset_values: Iterable, benchmark_values: Iterable, periods: int) -> Decimal | None:
    asset_momentum = calculate_momentum(asset_values, periods)
    benchmark_momentum = calculate_momentum(benchmark_values, periods)
    if asset_momentum is None or benchmark_momentum is None:
        return None
    return to_decimal(asset_momentum - benchmark_momentum)


def calculate_anomaly_score(value, peers: Iterable) -> Decimal | None:
    return calculate_zscore(value, peers)


def score_linear(value, *, low: float, high: float, invert: bool = False) -> float | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    if high == low:
        return 50.0
    raw = (numeric - low) / (high - low)
    raw = max(0.0, min(1.0, raw))
    if invert:
        raw = 1.0 - raw
    return raw * 100


def weighted_score(parts: list[tuple[float | None, float]], *, neutral: float = 50.0, missing_weight_factor: float = 0.35) -> Decimal:
    total = 0.0
    weights = 0.0
    for value, weight in parts:
        effective_value = neutral if value is None else max(0.0, min(100.0, float(value)))
        effective_weight = weight * (missing_weight_factor if value is None else 1.0)
        total += effective_value * effective_weight
        weights += effective_weight
    if weights == 0:
        return Decimal("50.000000")
    return to_decimal(max(0.0, min(100.0, total / weights))) or Decimal("50.000000")

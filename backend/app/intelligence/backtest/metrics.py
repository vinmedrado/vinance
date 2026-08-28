from __future__ import annotations

import math
from collections.abc import Iterable
from decimal import Decimal

TRADING_DAYS_PER_YEAR = 252


def _to_float_series(values: Iterable[float | int | Decimal | None]) -> list[float]:
    cleaned: list[float] = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            cleaned.append(number)
    return cleaned


def total_return(prices: Iterable[float | int | Decimal | None]) -> float | None:
    """Retorno acumulado entre o primeiro e o último preço válido."""
    series = _to_float_series(prices)
    if len(series) < 2 or series[0] <= 0:
        return None
    return (series[-1] / series[0]) - 1


def annualized_return(prices: Iterable[float | int | Decimal | None], *, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Retorno anualizado assumindo periodicidade diária de pregão por padrão."""
    series = _to_float_series(prices)
    cumulative = total_return(series)
    if cumulative is None or len(series) < 2:
        return None
    years = (len(series) - 1) / periods_per_year
    if years <= 0 or cumulative <= -1:
        return None
    return (1 + cumulative) ** (1 / years) - 1


def period_returns(prices: Iterable[float | int | Decimal | None]) -> list[float]:
    series = _to_float_series(prices)
    returns: list[float] = []
    for previous, current in zip(series, series[1:]):
        if previous > 0:
            returns.append((current / previous) - 1)
    return returns


def volatility(returns: Iterable[float | int | Decimal | None], *, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Volatilidade anualizada sobre uma série de retornos periódicos."""
    series = _to_float_series(returns)
    if len(series) < 2:
        return None
    mean = sum(series) / len(series)
    variance = sum((value - mean) ** 2 for value in series) / (len(series) - 1)
    return math.sqrt(variance) * math.sqrt(periods_per_year)


def sharpe_ratio(returns: Iterable[float | int | Decimal | None], *, risk_free_rate: float = 0.0, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float | None:
    """Sharpe simplificado, sem benchmark complexo nesta fase."""
    series = _to_float_series(returns)
    if len(series) < 2:
        return None
    vol = volatility(series, periods_per_year=periods_per_year)
    if vol is None or vol == 0:
        return None
    excess_daily = (sum(series) / len(series)) - (risk_free_rate / periods_per_year)
    return (excess_daily * periods_per_year) / vol


def max_drawdown(prices: Iterable[float | int | Decimal | None]) -> float | None:
    """Maior queda percentual do pico ao vale da série."""
    series = _to_float_series(prices)
    if len(series) < 2:
        return None
    peak = series[0]
    worst = 0.0
    for price in series:
        if price > peak:
            peak = price
        if peak > 0:
            drawdown = (price / peak) - 1
            worst = min(worst, drawdown)
    return worst


def win_rate(returns: Iterable[float | int | Decimal | None]) -> float | None:
    series = _to_float_series(returns)
    if not series:
        return None
    return sum(1 for value in series if value > 0) / len(series)


def hit_rate_top_n(selected_returns: Iterable[float | int | Decimal | None], universe_returns: Iterable[float | int | Decimal | None] | None = None) -> float | None:
    """Taxa de acerto simples: top N com retorno positivo.

    Quando uma série de universo é fornecida, mede a fração de selecionados acima da mediana do universo.
    Sem universo, mede retorno positivo. Isso evita benchmark complexo na Fase 19.
    """
    selected = _to_float_series(selected_returns)
    if not selected:
        return None
    universe = _to_float_series(universe_returns or [])
    if universe:
        ordered = sorted(universe)
        median = ordered[len(ordered) // 2]
        return sum(1 for value in selected if value >= median) / len(selected)
    return win_rate(selected)

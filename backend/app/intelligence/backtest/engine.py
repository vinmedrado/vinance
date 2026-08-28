from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean
from typing import Iterable

from backend.app.intelligence.backtest.metrics import (
    annualized_return,
    hit_rate_top_n,
    max_drawdown,
    period_returns,
    sharpe_ratio,
    total_return,
    volatility,
    win_rate,
)


@dataclass(frozen=True)
class FeaturePoint:
    ticker: str
    date: date
    score_final: Decimal | float | int | None


@dataclass(frozen=True)
class PricePoint:
    ticker: str
    date: date
    close: Decimal | float | int | None


@dataclass(frozen=True)
class BacktestTrade:
    ticker: str
    signal_date: date
    entry_date: date
    exit_date: date
    score_final: float
    entry_price: float
    exit_price: float
    return_pct: float


def _rebalance_dates(start_date: date, end_date: date, frequency: str) -> list[date]:
    step_days = {"daily": 1, "weekly": 7, "monthly": 30}.get(frequency, 30)
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=step_days)
    return dates


def _score(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _first_price_on_or_after(prices: list[PricePoint], target: date) -> PricePoint | None:
    for price in prices:
        if price.date >= target and price.close is not None and float(price.close) > 0:
            return price
    return None


def _price_series_between(prices: list[PricePoint], start: date, end: date) -> list[float]:
    return [float(price.close) for price in prices if start <= price.date <= end and price.close is not None and float(price.close) > 0]


def run_ranking_backtest(
    *,
    market: str,
    features: Iterable[FeaturePoint],
    prices: Iterable[PricePoint],
    start_date: date,
    end_date: date,
    holding_period_days: int = 90,
    top_n: int = 5,
    rebalance_frequency: str = "monthly",
) -> dict:
    """Executa backtest on-demand de ranking por score_final.

    O ranking usa apenas features com data menor ou igual à data de rebalanceamento. O retorno é calculado
    somente depois da data do sinal, evitando lookahead bias óbvio nesta camada base.
    """
    warnings: list[str] = []
    trades: list[BacktestTrade] = []
    features_by_date: dict[date, list[FeaturePoint]] = defaultdict(list)
    prices_by_ticker: dict[str, list[PricePoint]] = defaultdict(list)

    for feature in features:
        score = _score(feature.score_final)
        if score is None:
            continue
        features_by_date[feature.date].append(feature)
    for price in prices:
        prices_by_ticker[price.ticker.upper()].append(price)
    for ticker in prices_by_ticker:
        prices_by_ticker[ticker].sort(key=lambda item: item.date)

    if not features_by_date:
        warnings.append("Nenhuma feature com score_final disponível para o período solicitado.")
    if not prices_by_ticker:
        warnings.append("Nenhum preço disponível para o período solicitado.")

    available_feature_dates = sorted(features_by_date)
    for signal_date in _rebalance_dates(start_date, end_date, rebalance_frequency):
        valid_dates = [item for item in available_feature_dates if item <= signal_date]
        if not valid_dates:
            warnings.append(f"Sem ranking disponível em ou antes de {signal_date.isoformat()}.")
            continue
        ranking_date = valid_dates[-1]
        ranking = sorted(
            features_by_date[ranking_date],
            key=lambda item: float(item.score_final or 0),
            reverse=True,
        )[:top_n]
        for feature in ranking:
            ticker = feature.ticker.upper()
            ticker_prices = prices_by_ticker.get(ticker, [])
            entry = _first_price_on_or_after(ticker_prices, signal_date + timedelta(days=1))
            exit_target = signal_date + timedelta(days=holding_period_days)
            exit_price = _first_price_on_or_after(ticker_prices, exit_target)
            if entry is None or exit_price is None:
                warnings.append(f"{ticker}: preço insuficiente para janela futura de {holding_period_days} dias em {signal_date.isoformat()}.")
                continue
            entry_value = float(entry.close or 0)
            exit_value = float(exit_price.close or 0)
            if entry_value <= 0:
                warnings.append(f"{ticker}: preço de entrada inválido em {entry.date.isoformat()}.")
                continue
            trades.append(
                BacktestTrade(
                    ticker=ticker,
                    signal_date=signal_date,
                    entry_date=entry.date,
                    exit_date=exit_price.date,
                    score_final=float(feature.score_final or 0),
                    entry_price=entry_value,
                    exit_price=exit_value,
                    return_pct=(exit_value / entry_value) - 1,
                )
            )

    trade_returns = [trade.return_pct for trade in trades]
    # Série de capital igualmente ponderada por trade fechado; suficiente para validação quantitativa base.
    equity_curve = [1.0]
    for return_pct in trade_returns:
        equity_curve.append(equity_curve[-1] * (1 + return_pct))

    metrics = {
        "total_return": total_return(equity_curve),
        "annualized_return": annualized_return(equity_curve),
        "volatility": volatility(trade_returns),
        "sharpe_ratio": sharpe_ratio(trade_returns),
        "max_drawdown": max_drawdown(equity_curve),
        "win_rate": win_rate(trade_returns),
        "hit_rate_top_n": hit_rate_top_n(trade_returns),
    }
    return {
        "market": market,
        "metrics": metrics,
        "warnings": warnings[:100],
        "sample_size": len(trades),
        "trades": trades,
        "methodology": [
            "Backtest on-demand sem persistência de resultados nesta fase.",
            "Ranking formado por score_final disponível em ou antes da data de rebalanceamento.",
            "Entrada ocorre após a data do sinal para evitar lookahead bias óbvio.",
            "Sem custos, impostos, slippage, alavancagem ou benchmark complexo nesta versão base.",
            "Não há ML treinado; score_final é heurístico baseado em features quantitativas.",
        ],
    }

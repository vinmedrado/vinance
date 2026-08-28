from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.trading.paper_trading_v2.models import MarketCandle, PaperTrade, PortfolioSnapshot
from backend.trading.prediction_engine.models import PredictionResult


class HistoricalCandle:
    def __init__(
        self,
        candle: MarketCandle | None = None,
        features: dict[str, Any] | None = None,
        *,
        candle_id: int | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        open_time: datetime | None = None,
        open: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float | None = None,
    ) -> None:
        if candle is None:
            if None in {candle_id, symbol, interval, open_time, open, high, low, close}:
                raise ValueError("Either candle or all candle fields must be provided.")
            candle = MarketCandle(
                candle_id=int(candle_id),
                symbol=str(symbol),
                interval=str(interval),
                open_time=open_time,
                open=float(open),
                high=float(high),
                low=float(low),
                close=float(close),
            )
        self.candle = candle
        self.features = features or {}

    @property
    def candle_id(self) -> int:
        return self.candle.candle_id

    @property
    def symbol(self) -> str:
        return self.candle.symbol

    @property
    def interval(self) -> str:
        return self.candle.interval

    @property
    def open_time(self) -> datetime:
        return self.candle.open_time

    @property
    def open(self) -> float:
        return self.candle.open

    @property
    def high(self) -> float:
        return self.candle.high

    @property
    def low(self) -> float:
        return self.candle.low

    @property
    def close(self) -> float:
        return self.candle.close


@dataclass(frozen=True)
class BacktestDataset:
    candles: tuple[HistoricalCandle, ...]
    symbol: str
    interval: str
    feature_version: str


@dataclass(frozen=True)
class BacktestRunContext:
    run_id: str
    symbol: str
    interval: str
    target_name: str
    model_name: str
    model_version: str
    feature_version: str
    prediction_engine_version: str
    paper_trading_engine_version: str
    start_time: datetime | None
    end_time: datetime | None
    take_profit_threshold: float
    stop_loss_threshold: float
    output_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoricalPrediction:
    history_index: int
    candle_id: int
    open_time: datetime
    predicted_class: int
    probability_stop_loss: float
    probability_neutral: float
    probability_take_profit: float
    confidence: float
    confidence_level: str


@dataclass
class BacktestResult:
    context: BacktestRunContext
    metrics: dict[str, Any]
    trades: list[PaperTrade]
    equity_curve: list[PortfolioSnapshot]
    drawdown_curve: list[dict[str, Any]]
    daily_results: list[dict[str, Any]]
    monthly_results: list[dict[str, Any]]
    signal_analysis: dict[str, Any]
    predictions: list[PredictionResult] = field(default_factory=list)
    blocked_reasons: dict[str, int] = field(default_factory=dict)
    reports: dict[str, Path] = field(default_factory=dict)
    threshold_comparison: list[dict[str, Any]] = field(default_factory=list)
    baseline_comparison: dict[str, Any] | list[dict[str, Any]] = field(default_factory=dict)
    walk_forward_results: dict[str, Any] | list[dict[str, Any]] = field(default_factory=dict)
    prediction_cache: tuple[HistoricalPrediction, ...] = field(default_factory=tuple)
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def metadata(self) -> dict[str, Any]:
        return self.context.metadata | {"run_id": self.context.run_id, "candles_processed": len(self.predictions)}

    @property
    def report_paths(self) -> dict[str, Path]:
        return self.reports

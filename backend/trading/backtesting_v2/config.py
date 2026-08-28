from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend.trading.paper_trading_v2.config import PaperTradingConfig


BACKTESTING_ENGINE_VERSION = "v2"
STOP_LOSS_FIRST = "STOP_LOSS_FIRST"
TAKE_PROFIT_FIRST = "TAKE_PROFIT_FIRST"
WORST_CASE = "WORST_CASE"
BEST_CASE = "BEST_CASE"


@dataclass(frozen=True)
class WalkForwardConfig:
    enabled: bool = True
    window_count: int = 3
    mode: str = "expanding"
    train_size: int | None = None
    validation_size: int | None = None
    test_size: int | None = None
    step_size: int | None = None
    min_segment_candles: int = 20
    take_profit_thresholds: tuple[float, ...] = (0.50, 0.55, 0.60, 0.65, 0.70)
    stop_loss_thresholds: tuple[float, ...] = (0.50, 0.55, 0.60, 0.65, 0.70)
    selection_criterion: str = "sharpe_drawdown_net_profit"
    retrain_per_window: bool = False

    def __post_init__(self) -> None:
        if self.window_count < 1:
            raise ValueError("walk_forward.window_count must be positive")
        if self.mode not in {"expanding", "rolling"}:
            raise ValueError("walk_forward.mode must be expanding or rolling")
        sizes = [value for value in (self.train_size, self.validation_size, self.test_size) if value is not None]
        if sizes and len(sizes) != 3:
            raise ValueError("walk-forward fixed sizes must all be provided")
        if any(value <= 0 for value in sizes):
            raise ValueError("walk-forward sizes must be positive")
        if self.step_size is not None and self.step_size <= 0:
            raise ValueError("walk_forward.step_size must be positive")
        if self.min_segment_candles < 1:
            raise ValueError("walk_forward.min_segment_candles must be positive")
        if self.selection_criterion not in {
            "sharpe_drawdown_net_profit",
            "net_profit",
            "profit_factor",
            "expectancy",
        }:
            raise ValueError("unsupported walk-forward selection_criterion")
        for values in (self.take_profit_thresholds, self.stop_loss_thresholds):
            if not values or any(value < 0 or value > 1 for value in values):
                raise ValueError("walk-forward thresholds must be between 0 and 1")

    @property
    def threshold_pairs(self) -> tuple[tuple[float, float], ...]:
        return tuple(
            (tp, sl)
            for tp in self.take_profit_thresholds
            for sl in self.stop_loss_thresholds
        )


@dataclass(frozen=True)
class BacktestingConfig:
    engine_version: str = BACKTESTING_ENGINE_VERSION
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    exchange: str = "BINANCE"
    target_name: str = "v2_long_tp_100bps_sl_50bps_h_24"
    feature_version: str = "v2"
    prediction_engine_version: str = "v2"
    output_root: Path = Path("backend/trading/output/backtesting_v2")
    artifacts_root: Path = Path("backend/trading/artifacts/ml_engine_v2")
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_period_candles: int = 1
    min_candles: int | None = None
    limit: int | None = None
    max_candles: int | None = None
    initial_capital: float = 10_000.0
    take_profit_thresholds: tuple[float, ...] = (0.60,)
    stop_loss_thresholds: tuple[float, ...] = (0.60,)
    confidence_threshold: float | None = None
    intracandle_policy: str = STOP_LOSS_FIRST
    seed: int = 42
    overwrite: bool = True
    paper_only: bool = True
    commit_hash: str | None = None
    timestamp: str | None = None
    show_progress: bool = False
    paper_config: PaperTradingConfig = field(default_factory=PaperTradingConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)

    def __post_init__(self) -> None:
        if not self.paper_only or not self.paper_config.paper_only:
            raise RuntimeError("Backtesting V2 must run with PAPER_ONLY=True.")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.min_candles is not None:
            object.__setattr__(self, "min_period_candles", self.min_candles)
        if self.min_period_candles < 1:
            raise ValueError("min_period_candles must be at least 1")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be positive when provided")
        if self.max_candles is not None and self.max_candles < 1:
            raise ValueError("max_candles must be positive when provided")
        if self.limit is not None and self.max_candles is not None and self.limit != self.max_candles:
            raise ValueError("limit and max_candles must match when both are provided")
        if self.max_candles is None and self.limit is not None:
            object.__setattr__(self, "max_candles", self.limit)
        if self.intracandle_policy not in {STOP_LOSS_FIRST, TAKE_PROFIT_FIRST, WORST_CASE, BEST_CASE}:
            raise ValueError(f"Unsupported intracandle_policy: {self.intracandle_policy}")
        if not self.target_name.startswith("v2_"):
            raise ValueError("Backtesting V2 only supports target v2 in the initial scope")
        for label, values in (
            ("take_profit_thresholds", self.take_profit_thresholds),
            ("stop_loss_thresholds", self.stop_loss_thresholds),
        ):
            if not values:
                raise ValueError(f"{label} must not be empty")
            invalid = [value for value in values if not 0 <= value <= 1]
            if invalid:
                raise ValueError(f"{label} contains invalid thresholds: {invalid}")
        costs = {
            "fee_bps": self.paper_config.fee_bps,
            "slippage_bps": self.paper_config.slippage_bps,
            "spread_bps": self.paper_config.spread_bps,
        }
        for name, value in costs.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        normalized_paper = PaperTradingConfig(
            engine_version=self.paper_config.engine_version,
            initial_capital=self.initial_capital,
            quote_asset=self.paper_config.quote_asset,
            output_root=self.paper_config.output_root,
            min_confidence=self.confidence_threshold
            if self.confidence_threshold is not None
            else self.paper_config.min_confidence,
            fixed_fraction=self.paper_config.fixed_fraction,
            max_open_positions=self.paper_config.max_open_positions,
            max_daily_loss=self.paper_config.max_daily_loss,
            max_position_size=self.paper_config.max_position_size,
            max_capital_per_trade=self.paper_config.max_capital_per_trade,
            cooldown_candles=self.paper_config.cooldown_candles,
            fee_bps=self.paper_config.fee_bps,
            slippage_bps=self.paper_config.slippage_bps,
            spread_bps=self.paper_config.spread_bps,
            paper_only=True,
            feature_version=self.feature_version,
            target_version="v2",
        )
        object.__setattr__(self, "paper_config", normalized_paper)

    @property
    def threshold_pairs(self) -> tuple[tuple[float, float], ...]:
        return tuple((tp, sl) for tp in self.take_profit_thresholds for sl in self.stop_loss_thresholds)

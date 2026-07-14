from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PAPER_TRADING_ENGINE_VERSION = "v2"


@dataclass(frozen=True)
class PaperTradingConfig:
    engine_version: str = PAPER_TRADING_ENGINE_VERSION
    initial_capital: float = 10_000.0
    quote_asset: str = "USDT"
    output_root: Path = Path("backend/trading/output/paper_trading_v2")
    min_confidence: float = 0.60
    fixed_fraction: float = 0.02
    max_open_positions: int = 3
    max_daily_loss: float = 0.05
    max_position_size: float = 0.10
    max_capital_per_trade: float = 0.10
    cooldown_candles: int = 1
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    spread_bps: float = 2.0
    paper_only: bool = True
    feature_version: str = "v2"
    target_version: str = "v2"

    def __post_init__(self) -> None:
        positive = {
            "initial_capital": self.initial_capital,
            "fixed_fraction": self.fixed_fraction,
            "max_position_size": self.max_position_size,
            "max_capital_per_trade": self.max_capital_per_trade,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        for name, value in {
            "min_confidence": self.min_confidence,
            "max_daily_loss": self.max_daily_loss,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.cooldown_candles < 0:
            raise ValueError("cooldown_candles must be non-negative")


DEFAULT_CONFIG = PaperTradingConfig()

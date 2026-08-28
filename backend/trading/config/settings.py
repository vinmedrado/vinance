from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    trading_mode: Literal["PAPER_ONLY", "LIVE_RESEARCH"] = "PAPER_ONLY"
    trading_exchange: str = "binance"
    trading_symbols_raw: str = Field("BTCUSDT,ETHUSDT", alias="TRADING_SYMBOLS")
    trading_interval: str = "5m"
    trading_lookback_days: int = 365
    trading_fee_bps: float = 10.0
    trading_slippage_bps: float = 5.0
    trading_max_position_pct: float = 0.05
    trading_max_daily_loss_pct: float = 0.02
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def trading_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.trading_symbols_raw.split(",") if s.strip()]


@lru_cache
def get_settings() -> TradingSettings:
    return TradingSettings()

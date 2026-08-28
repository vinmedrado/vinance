from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


HISTORY_EXPANSION_VERSION = "v2"
INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "1h": 3_600,
    "2h": 7_200,
    "4h": 14_400,
    "6h": 21_600,
    "8h": 28_800,
    "12h": 43_200,
    "1d": 86_400,
}
PREFERRED_ASSETS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")
PREFERRED_INTERVALS = ("5m", "15m", "1h", "4h")


@dataclass(frozen=True)
class HistoryExpansionConfig:
    version: str = HISTORY_EXPANSION_VERSION
    exchange: str = "binance"
    history_months: int = 24
    minimum_history_months: int = 12
    history_days_override: int | None = None
    page_limit: int = 1_000
    persistence_batch_size: int = 5_000
    request_pause_seconds: float = 0.10
    max_gap_percentage: float = 0.10
    output_root: Path = Path("backend/trading/history_expansion_v2/output")
    preferred_assets: tuple[str, ...] = PREFERRED_ASSETS
    preferred_intervals: tuple[str, ...] = PREFERRED_INTERVALS
    paper_only: bool = True

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise RuntimeError("History Expansion V2 requires PAPER_ONLY=True.")
        if not 12 <= self.history_months <= 24:
            raise ValueError("history_months must be between 12 and 24")
        if not 12 <= self.minimum_history_months <= self.history_months:
            raise ValueError("minimum_history_months must be between 12 and history_months")
        if self.history_days_override is not None and self.history_days_override < 1:
            raise ValueError("history_days_override must be positive")
        if not 1 <= self.page_limit <= 1_000:
            raise ValueError("page_limit must be between 1 and 1000")
        if self.persistence_batch_size < 100:
            raise ValueError("persistence_batch_size must be at least 100")
        if self.request_pause_seconds < 0:
            raise ValueError("request_pause_seconds cannot be negative")
        if not 0 <= self.max_gap_percentage <= 100:
            raise ValueError("max_gap_percentage must be between 0 and 100")

    @property
    def target_history_days(self) -> int:
        if self.history_days_override is not None:
            return self.history_days_override
        return int(round(self.history_months * 365.25 / 12.0))

    def interval_seconds(self, interval: str) -> int:
        try:
            return INTERVAL_SECONDS[interval]
        except KeyError as exc:
            raise ValueError(f"Unsupported Binance interval: {interval}") from exc

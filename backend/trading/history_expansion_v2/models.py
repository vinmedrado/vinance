from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, order=True)
class HistoryScope:
    exchange: str
    symbol: str
    interval: str

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.symbol}:{self.interval}"


@dataclass(frozen=True)
class HistorySnapshot:
    scope: HistoryScope
    candle_count: int
    first_candle: datetime | None
    last_candle: datetime | None


@dataclass(frozen=True)
class GapRange:
    start: datetime
    end: datetime
    missing_candles: int


@dataclass(frozen=True)
class DownloadBatch:
    frame: Any
    duplicates_removed: int = 0


@dataclass
class DownloadStats:
    requested_ranges: int = 0
    requests: int = 0
    downloaded_rows: int = 0
    persisted_rows: int = 0
    duplicates_removed: int = 0


@dataclass(frozen=True)
class IntegrityResult:
    scope: HistoryScope
    candle_count: int
    first_candle: datetime | None
    last_candle: datetime | None
    coverage_seconds: float
    coverage_months: float
    expected_candles: int
    missing_candles: int
    gap_count: int
    gap_percentage: float
    duplicate_count: int
    duplicates_removed: int
    duplicate_percentage: float
    invalid_timestamps: int
    timezone_invalid: int
    chronological_violations: int
    timestamp_alignment_violations: int
    invalid_ohlc: int
    invalid_volume: int
    integrity_score: float
    integrity_final: bool
    gaps: tuple[GapRange, ...] = ()


@dataclass
class ExpansionCaseResult:
    scope: HistoryScope
    status: str = "pending"
    old_candles: int = 0
    new_candles: int = 0
    final_candles: int = 0
    duplicates_removed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    integrity: IntegrityResult | None = None
    feature_store: dict[str, Any] | None = None
    target_engine: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class ExpansionResult:
    run_id: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    cases: list[ExpansionCaseResult] = field(default_factory=list)
    output_root: str = ""

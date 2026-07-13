from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .config import TargetSpec


@dataclass(frozen=True)
class TargetBuildResult:
    frame: pd.DataFrame
    specs: tuple[TargetSpec, ...]
    target_version: str
    target_columns: tuple[str, ...]


@dataclass(frozen=True)
class TargetPipelineResult:
    symbol: str
    interval: str
    target_version: str
    candles_loaded: int
    rows_built: int
    targets_persisted: int
    target_names: tuple[str, ...]
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    latest_candle_time: datetime | None = None
    last_target_time_before_run: datetime | None = None
    metadata: dict[str, int | float | str] = field(default_factory=dict)

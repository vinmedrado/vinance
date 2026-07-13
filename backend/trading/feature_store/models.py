from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pandas as pd


IndicatorFunction = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    category: str
    columns: tuple[str, ...]
    function: IndicatorFunction
    lookback: int
    description: str


@dataclass(frozen=True)
class FeatureSet:
    version: str
    definitions: tuple[FeatureDefinition, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        seen: list[str] = []
        for definition in self.definitions:
            for column in definition.columns:
                if column not in seen:
                    seen.append(column)
        return tuple(seen)

    @property
    def max_lookback(self) -> int:
        return max((definition.lookback for definition in self.definitions), default=0)


@dataclass(frozen=True)
class FeatureBuildResult:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    version: str
    warmup_candles: int


@dataclass(frozen=True)
class PipelineRunResult:
    symbol: str
    interval: str
    feature_version: str
    candles_loaded: int
    rows_built: int
    rows_persisted: int
    feature_count: int
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    latest_candle_time: datetime | None = None
    last_feature_time_before_run: datetime | None = None
    null_counts: dict[str, int] = field(default_factory=dict)

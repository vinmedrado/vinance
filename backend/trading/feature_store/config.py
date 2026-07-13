from __future__ import annotations

from dataclasses import dataclass, field


FEATURE_VERSION = "v2"

REQUIRED_CANDLE_COLUMNS = (
    "id",
    "exchange",
    "symbol",
    "interval",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True)
class FeatureStoreConfig:
    feature_version: str = FEATURE_VERSION
    warmup_candles: int = 260
    default_limit: int = 100_000
    min_non_null_features: int = 5
    source_table: str = "crypto_candles"
    sink_table: str = "crypto_features"
    required_columns: tuple[str, ...] = field(default=REQUIRED_CANDLE_COLUMNS)


DEFAULT_CONFIG = FeatureStoreConfig()

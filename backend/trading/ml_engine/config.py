from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ML_ENGINE_VERSION = "v2"

PROHIBITED_FEATURE_COLUMNS = {
    "candle_id",
    "id",
    "open_time",
    "close_time",
    "target_class",
    "target_value",
    "target_name",
    "horizon_candles",
    "threshold_pct",
    "future_return",
}


@dataclass(frozen=True)
class SplitConfig:
    train_pct: float = 0.70
    validation_pct: float = 0.15
    test_pct: float = 0.15

    def __post_init__(self) -> None:
        total = self.train_pct + self.validation_pct + self.test_pct
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Temporal split percentages must sum to 1.0")


@dataclass(frozen=True)
class MLEngineConfig:
    feature_version: str = "v2"
    target_prefix: str = "v2_"
    ml_engine_version: str = ML_ENGINE_VERSION
    min_samples: int = 300
    min_class_count: int = 10
    best_metric: str = "f1_macro"
    probability_thresholds: tuple[float, ...] = (0.55, 0.60, 0.65, 0.70, 0.75)
    split: SplitConfig = field(default_factory=SplitConfig)
    artifacts_root: Path = Path("backend/trading/artifacts/ml_engine_v2")
    random_state: int = 42


DEFAULT_CONFIG = MLEngineConfig()

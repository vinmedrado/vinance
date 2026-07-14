from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PREDICTION_ENGINE_VERSION = "v2"


@dataclass(frozen=True)
class PredictionEngineConfig:
    feature_version: str = "v2"
    prediction_engine_version: str = PREDICTION_ENGINE_VERSION
    artifacts_root: Path = Path("backend/trading/artifacts/ml_engine_v2")
    output_root: Path = Path("backend/trading/output/prediction_engine_v2")
    take_profit_threshold: float = 0.60
    stop_loss_threshold: float = 0.60
    paper_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("take_profit_threshold", self.take_profit_threshold),
            ("stop_loss_threshold", self.stop_loss_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")


DEFAULT_CONFIG = PredictionEngineConfig()

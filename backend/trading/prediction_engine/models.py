from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PredictionInput:
    candle_id: int
    symbol: str
    interval: str
    open_time: datetime
    close: float
    features: dict[str, Any]


@dataclass(frozen=True)
class ManifestEntry:
    symbol: str
    interval: str
    target_name: str
    model_name: str
    feature_version: str
    ml_engine_version: str
    is_best: bool
    artifact_dir: Path
    generated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedArtifacts:
    entry: ManifestEntry
    model: Any
    preprocessing: Any
    feature_columns: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PredictionProbabilities:
    probability_stop_loss: float
    probability_neutral: float
    probability_take_profit: float

    @property
    def confidence(self) -> float:
        return max(self.probability_stop_loss, self.probability_neutral, self.probability_take_profit)

    def as_dict(self) -> dict[str, float]:
        return {
            "probability_stop_loss": self.probability_stop_loss,
            "probability_neutral": self.probability_neutral,
            "probability_take_profit": self.probability_take_profit,
        }


@dataclass(frozen=True)
class PredictionResult:
    prediction_id: str
    symbol: str
    interval: str
    target_name: str
    candle_id: int
    open_time: datetime
    model_name: str
    artifact_dir: Path
    predicted_class: int
    probability_stop_loss: float
    probability_neutral: float
    probability_take_profit: float
    confidence: float
    confidence_level: str
    decision: str
    prediction_engine_version: str
    model_version: str
    feature_version: str
    risk_score: float
    expected_return: float
    expected_drawdown: float
    position_size: None = None
    loaded_manifest: dict[str, Any] = field(default_factory=dict)
    reason: dict[str, Any] = field(default_factory=dict)
    report_path: Path | None = None

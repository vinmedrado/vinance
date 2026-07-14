from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TradingDataset:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    symbol: str
    interval: str
    target_name: str

    @property
    def sample_count(self) -> int:
        return int(len(self.frame))

    @property
    def class_distribution(self) -> dict[int, int]:
        counts = self.frame["target_class"].value_counts().sort_index()
        return {int(label): int(count) for label, count in counts.items()}


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class PreprocessingBundle:
    feature_columns: tuple[str, ...]
    medians: dict[str, float]

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        features = frame.loc[:, list(self.feature_columns)].copy()
        for column, value in self.medians.items():
            features[column] = pd.to_numeric(features[column], errors="coerce").fillna(value)
        return features


@dataclass(frozen=True)
class ModelEvaluation:
    model_name: str
    metrics: dict[str, Any]
    operational_metrics: dict[str, Any]
    predictions: np.ndarray
    probabilities: np.ndarray | None


@dataclass(frozen=True)
class TrainedModel:
    model_name: str
    estimator: Any
    preprocessing: PreprocessingBundle
    validation: ModelEvaluation
    test: ModelEvaluation | None = None
    calibrated: bool = False


@dataclass(frozen=True)
class TrainingReport:
    symbol: str
    interval: str
    target_name: str
    sample_count: int
    feature_count: int
    class_distribution: dict[int, int]
    model_reports: dict[str, dict[str, Any]]
    best_model_name: str
    best_model_path: Path
    generated_at: datetime
    manifest_entry: dict[str, Any] = field(default_factory=dict)

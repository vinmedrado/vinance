from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from .models import PreprocessingBundle


def fit_preprocessing(train: pd.DataFrame, feature_columns: tuple[str, ...]) -> PreprocessingBundle:
    medians: dict[str, float] = {}
    for column in feature_columns:
        values = pd.to_numeric(train[column], errors="coerce")
        median = values.median()
        medians[column] = 0.0 if pd.isna(median) else float(median)
    return PreprocessingBundle(feature_columns=feature_columns, medians=medians)


def train_estimator(estimator, preprocessing: PreprocessingBundle, train: pd.DataFrame):
    x_train = preprocessing.transform(train)
    y_train = train["target_class"].astype(int)
    estimator.fit(x_train, y_train)
    return estimator


def validate_training_data(train: pd.DataFrame, *, min_class_count: int) -> None:
    counts = train["target_class"].value_counts()
    if len(counts) < 2:
        raise ValueError("Training data must contain at least two classes.")
    too_small = {int(label): int(count) for label, count in counts.items() if count < min_class_count}
    if too_small:
        raise ValueError(f"Training classes below minimum count: {too_small}")


def select_best_model(results: Mapping[str, object], metric: str) -> str:
    if not results:
        raise ValueError("No model results available.")
    best_name = None
    best_value = None
    for name, trained in results.items():
        value = trained.validation.metrics.get(metric)  # type: ignore[attr-defined]
        if value is None:
            continue
        if best_value is None or value > best_value:
            best_name = name
            best_value = value
    if best_name is None:
        raise ValueError(f"No model produced metric {metric!r}.")
    return best_name

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class BaselineResult:
    model: Pipeline
    metrics: dict[str, object]


def train_baseline(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    feature_columns: list[str],
    target_column: str = "target_class",
) -> BaselineResult:
    train_binary = train[train[target_column].isin([0, 1])].dropna(subset=feature_columns + [target_column])
    valid_binary = validation[validation[target_column].isin([0, 1])].dropna(subset=feature_columns + [target_column])
    if train_binary.empty or valid_binary.empty:
        raise ValueError("Treino ou validação sem dados suficientes.")

    model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    model.fit(train_binary[feature_columns], train_binary[target_column])
    probabilities = model.predict_proba(valid_binary[feature_columns])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "roc_auc": float(roc_auc_score(valid_binary[target_column], probabilities)),
        "classification_report": classification_report(
            valid_binary[target_column], predictions, output_dict=True, zero_division=0
        ),
    }
    return BaselineResult(model=model, metrics=metrics)

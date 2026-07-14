from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .config import DEFAULT_CONFIG, MLEngineConfig
from .models import ModelEvaluation, PreprocessingBundle


def evaluate_model(
    *,
    model_name: str,
    estimator,
    preprocessing: PreprocessingBundle,
    frame: pd.DataFrame,
    config: MLEngineConfig = DEFAULT_CONFIG,
) -> ModelEvaluation:
    x_data = preprocessing.transform(frame)
    y_true = frame["target_class"].astype(int).to_numpy()
    labels = sorted(np.unique(y_true).tolist())
    predictions = estimator.predict(x_data)
    probabilities = _predict_probabilities(estimator, x_data)

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "precision_macro": float(precision_score(y_true, predictions, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, predictions, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, predictions, average="macro", zero_division=0)),
        "class_distribution": {int(k): int(v) for k, v in pd.Series(y_true).value_counts().sort_index().items()},
        "confusion_matrix": confusion_matrix(y_true, predictions, labels=labels).tolist(),
        "labels": labels,
    }
    if probabilities is not None:
        metrics.update(_probability_metrics(y_true, probabilities, labels))
    operational = operational_metrics(
        frame=frame,
        predictions=predictions,
        probabilities=probabilities,
        labels=labels,
        config=config,
    )
    return ModelEvaluation(
        model_name=model_name,
        metrics=_json_ready(metrics),
        operational_metrics=_json_ready(operational),
        predictions=predictions,
        probabilities=probabilities,
    )


def operational_metrics(
    *,
    frame: pd.DataFrame,
    predictions: np.ndarray,
    probabilities: np.ndarray | None,
    labels: list[int],
    config: MLEngineConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mean_return_by_predicted_class": {},
        "probability_bands": {},
        "confidence_all_classes": {},
        "majority_baseline": {},
    }
    target_values = pd.to_numeric(frame["target_value"], errors="coerce").to_numpy(dtype=float)
    for label in labels:
        mask = predictions == label
        result["mean_return_by_predicted_class"][str(label)] = float(np.nanmean(target_values[mask])) if mask.any() else None

    majority = int(frame["target_class"].value_counts().idxmax())
    majority_predictions = np.full(len(frame), majority)
    result["majority_baseline"] = {
        "class": majority,
        "accuracy": float(accuracy_score(frame["target_class"].astype(int), majority_predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(frame["target_class"].astype(int), majority_predictions)),
    }

    if probabilities is None:
        return result

    class_to_index = {label: index for index, label in enumerate(labels)}
    tp_index = class_to_index.get(1)
    max_probability = probabilities.max(axis=1)
    predicted_class = predictions.astype(int)
    true_class = frame["target_class"].astype(int).to_numpy()
    true_tp_count = int((true_class == 1).sum())
    predicted_tp_count = int((predicted_class == 1).sum())

    if tp_index is None:
        for threshold in config.probability_thresholds:
            confidence_mask = max_probability >= threshold
            result["probability_bands"][f"{threshold:.2f}"] = {
                "signals": 0,
                "tp_precision": None,
                "mean_return": None,
                "financial_expectancy": None,
                "predicted_tp_count": predicted_tp_count,
                "true_tp_count": true_tp_count,
                "tp_recall": None,
            }
            result["confidence_all_classes"][f"{threshold:.2f}"] = {
                "signals": int(confidence_mask.sum()),
                "mean_return": float(np.nanmean(target_values[confidence_mask])) if confidence_mask.any() else None,
                "predicted_class_distribution": {
                    str(label): int(((predicted_class == label) & confidence_mask).sum())
                    for label in labels
                },
            }
        return result

    tp_probability = probabilities[:, tp_index]

    for threshold in config.probability_thresholds:
        signal_mask = tp_probability >= threshold
        confidence_mask = max_probability >= threshold
        correct_tp = int(((true_class == 1) & signal_mask).sum())
        result["probability_bands"][f"{threshold:.2f}"] = {
            "signals": int(signal_mask.sum()),
            "tp_precision": float((true_class[signal_mask] == 1).mean()) if signal_mask.any() else None,
            "mean_return": float(np.nanmean(target_values[signal_mask])) if signal_mask.any() else None,
            "financial_expectancy": float(np.nanmean(target_values[signal_mask])) if signal_mask.any() else None,
            "predicted_tp_count": predicted_tp_count,
            "true_tp_count": true_tp_count,
            "tp_recall": correct_tp / true_tp_count if true_tp_count > 0 else None,
        }
        result["confidence_all_classes"][f"{threshold:.2f}"] = {
            "signals": int(confidence_mask.sum()),
            "mean_return": float(np.nanmean(target_values[confidence_mask])) if confidence_mask.any() else None,
            "predicted_class_distribution": {
                str(label): int(((predicted_class == label) & confidence_mask).sum())
                for label in labels
            },
        }
    return result


def _predict_probabilities(estimator, x_data: pd.DataFrame) -> np.ndarray | None:
    if hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(x_data)
    return None


def _probability_metrics(y_true: np.ndarray, probabilities: np.ndarray, labels: list[int]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "probability_distribution": {
            "max_mean": float(probabilities.max(axis=1).mean()),
            "max_p50": float(np.quantile(probabilities.max(axis=1), 0.50)),
            "max_p90": float(np.quantile(probabilities.max(axis=1), 0.90)),
        }
    }
    try:
        metrics["log_loss"] = float(log_loss(y_true, probabilities, labels=labels))
    except Exception:
        metrics["log_loss"] = None
    try:
        if len(labels) == 2:
            positive_index = labels.index(1) if 1 in labels else 1
            positive = (y_true == labels[positive_index]).astype(int)
            scores = probabilities[:, positive_index]
            metrics["roc_auc"] = float(roc_auc_score(positive, scores))
            metrics["pr_auc"] = float(average_precision_score(positive, scores))
        else:
            metrics["roc_auc"] = float(roc_auc_score(y_true, probabilities, labels=labels, multi_class="ovr", average="macro"))
            y_bin = np.column_stack([(y_true == label).astype(int) for label in labels])
            metrics["pr_auc"] = float(average_precision_score(y_bin, probabilities, average="macro"))
    except Exception:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
    return metrics


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    return value

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

from .models import PreprocessingBundle


def model_artifact_dir(root: Path, symbol: str, interval: str, target_name: str, model_name: str) -> Path:
    return root / symbol / interval / target_name / model_name


def save_artifacts(
    *,
    directory: Path,
    model,
    preprocessing: PreprocessingBundle,
    feature_columns: tuple[str, ...],
    metrics: dict[str, Any],
    confusion_matrix: list[list[int]],
    metadata: dict[str, Any],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, directory / "model.joblib")
    joblib.dump(preprocessing, directory / "preprocessing.joblib")
    write_json(directory / "feature_columns.json", list(feature_columns))
    write_json(directory / "metrics.json", metrics)
    write_json(directory / "confusion_matrix.json", confusion_matrix)
    write_json(directory / "metadata.json", metadata)


def load_model_artifacts(directory: Path):
    return joblib.load(directory / "model.joblib"), joblib.load(directory / "preprocessing.joblib")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

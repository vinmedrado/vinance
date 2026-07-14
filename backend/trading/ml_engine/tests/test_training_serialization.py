from __future__ import annotations

import numpy as np

from backend.trading.ml_engine.config import MLEngineConfig
from backend.trading.ml_engine.dataset import temporal_split
from backend.trading.ml_engine.evaluator import evaluate_model
from backend.trading.ml_engine.pipeline import MLEnginePipeline
from backend.trading.ml_engine.registry import model_registry
from backend.trading.ml_engine.repository import MLEngineRepository
from backend.trading.ml_engine.serialization import load_model_artifacts
from backend.trading.ml_engine.tests.helpers import synthetic_dataset
from backend.trading.ml_engine.trainer import fit_preprocessing, select_best_model, train_estimator


class FakeRepository:
    def __init__(self, dataset):
        self.dataset = dataset

    def load_dataset(self, *, symbol: str, interval: str, target_name: str, limit=None):
        return self.dataset


def test_imputation_uses_training_data_only() -> None:
    dataset = synthetic_dataset(120)
    split = temporal_split(dataset)
    split.validation.loc[:, "feature_c"] = 9999
    preprocessing = fit_preprocessing(split.train, dataset.feature_columns)
    assert preprocessing.medians["feature_c"] != 9999


def test_training_all_registry_models_and_best_selection() -> None:
    config = MLEngineConfig(min_samples=100, min_class_count=5)
    dataset = synthetic_dataset(180)
    split = temporal_split(dataset, config.split)
    results = {}
    for name, factory in model_registry(config).items():
        preprocessing = fit_preprocessing(split.train, dataset.feature_columns)
        estimator = train_estimator(factory(), preprocessing, split.train)
        evaluation = evaluate_model(
            model_name=name,
            estimator=estimator,
            preprocessing=preprocessing,
            frame=split.validation,
            config=config,
        )
        assert "f1_macro" in evaluation.metrics
        results[name] = type("Trained", (), {"validation": evaluation})()
    assert select_best_model(results, "f1_macro") in results


def test_pipeline_serialization_reload_prediction_equivalence_and_idempotent_artifacts(tmp_path) -> None:
    config = MLEngineConfig(
        min_samples=120,
        min_class_count=5,
        artifacts_root=tmp_path / "ml_engine_v2",
    )
    dataset = synthetic_dataset(220)
    pipeline = MLEnginePipeline(FakeRepository(dataset), config=config)  # type: ignore[arg-type]

    report1 = pipeline.train_target(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name, models=("logistic_regression", "random_forest"))
    report2 = pipeline.train_target(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name, models=("logistic_regression", "random_forest"))

    assert report1.best_model_path == report2.best_model_path
    model, preprocessing = load_model_artifacts(report2.best_model_path)
    split = temporal_split(dataset, config.split)
    x_test = preprocessing.transform(split.test)
    pred1 = model.predict(x_test)
    reloaded_model, reloaded_preprocessing = load_model_artifacts(report2.best_model_path)
    pred2 = reloaded_model.predict(reloaded_preprocessing.transform(split.test))
    assert np.array_equal(pred1, pred2)
    assert (report2.best_model_path / "model.joblib").exists()
    assert (report2.best_model_path / "metrics.json").exists()


def test_pipeline_walk_forward_runs_without_overlap(tmp_path) -> None:
    config = MLEngineConfig(min_samples=120, min_class_count=5, artifacts_root=tmp_path / "ml")
    dataset = synthetic_dataset(240)
    pipeline = MLEnginePipeline(FakeRepository(dataset), config=config)  # type: ignore[arg-type]
    reports = pipeline.walk_forward_validate(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name, windows=2)
    assert len(reports) == 2
    assert "validation" in reports[0]

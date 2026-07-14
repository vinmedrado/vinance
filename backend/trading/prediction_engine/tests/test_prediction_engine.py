from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import joblib
import pandas as pd
import sklearn

from backend.trading.ml_engine.config import MLEngineConfig
from backend.trading.ml_engine.pipeline import MLEnginePipeline
from backend.trading.ml_engine.serialization import read_json, write_json
from backend.trading.ml_engine.tests.helpers import synthetic_dataset
from backend.trading.prediction_engine.config import PredictionEngineConfig
from backend.trading.prediction_engine.decision import AVOID, BUY_CANDIDATE, HIGH, HOLD, LOW, MEDIUM, VERY_HIGH, confidence_level, decide
from backend.trading.prediction_engine.errors import PredictionArtifactError, PredictionCompatibilityError, PredictionFeatureError
from backend.trading.prediction_engine.loader import PredictionArtifactLoader
from backend.trading.prediction_engine.models import PredictionInput, PredictionProbabilities
from backend.trading.prediction_engine.pipeline import PredictionEngine
from backend.trading.prediction_engine.predictor import PredictionPredictor


class FakeTrainingRepository:
    def __init__(self, dataset):
        self.dataset = dataset

    def load_dataset(self, *, symbol: str, interval: str, target_name: str, limit=None):
        return self.dataset


class FakePredictionRepository:
    def __init__(self, inputs: list[PredictionInput]) -> None:
        self.inputs = inputs
        self.calls: list[tuple[str, str]] = []

    def load_latest_features(self, *, symbol: str, interval: str) -> PredictionInput:
        self.calls.append((symbol, interval))
        matching = [item for item in self.inputs if item.symbol == symbol and item.interval == interval]
        if not matching:
            raise LookupError("No matching input")
        return sorted(matching, key=lambda item: item.open_time, reverse=True)[0]


def _train_artifact(tmp_path, rows: int = 220):
    dataset = synthetic_dataset(rows)
    config = MLEngineConfig(
        min_samples=120,
        min_class_count=5,
        artifacts_root=tmp_path / "ml_engine_v2",
    )
    pipeline = MLEnginePipeline(FakeTrainingRepository(dataset), config=config)  # type: ignore[arg-type]
    report = pipeline.train_target(
        symbol="BTCUSDT",
        interval="5m",
        target_name=dataset.target_name,
        models=("logistic_regression", "random_forest"),
    )
    return dataset, report, config


def _prediction_input(dataset, index: int = -1, *, features: dict | None = None) -> PredictionInput:
    row = dataset.frame.iloc[index]
    payload = features if features is not None else {column: row[column] for column in dataset.feature_columns}
    return PredictionInput(
        candle_id=int(row["candle_id"]),
        symbol=dataset.symbol,
        interval=dataset.interval,
        open_time=row["open_time"].to_pydatetime(),
        close=100.0,
        features=payload,
    )


def _paper_settings():
    return SimpleNamespace(trading_mode="PAPER_ONLY", trading_interval="5m")


def test_manifest_loading_and_best_model_selection(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))

    manifest = loader.load_manifest()
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    assert manifest["models"]
    assert entry.model_name == report.best_model_name
    assert entry.artifact_dir == report.best_model_path
    assert entry.feature_version == "v2"
    assert entry.is_best is True


def test_artifact_loading_validates_feature_columns_and_metadata(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    artifacts = loader.load_artifacts(entry)

    assert artifacts.feature_columns == dataset.feature_columns
    assert tuple(artifacts.preprocessing.feature_columns) == artifacts.feature_columns
    assert artifacts.metadata["model_name"] == report.best_model_name
    assert read_json(report.best_model_path / "feature_columns.json") == list(artifacts.feature_columns)


def test_artifact_loading_fails_on_feature_columns_contract_mismatch(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    preprocessing = joblib.load(report.best_model_path / "preprocessing.joblib")
    joblib.dump(replace(preprocessing, feature_columns=("different_feature",)), report.best_model_path / "preprocessing.joblib")
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionArtifactError as exc:
        assert "feature_columns" in str(exc)
    else:
        raise AssertionError("Expected feature_columns contract mismatch")


def test_missing_feature_error_is_clear(tmp_path) -> None:
    dataset, _, ml_config = _train_artifact(tmp_path)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    artifacts = loader.load_artifacts(loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name))
    features = {column: dataset.frame.iloc[-1][column] for column in dataset.feature_columns}
    features.pop(dataset.feature_columns[0])

    try:
        PredictionPredictor().predict(_prediction_input(dataset, features=features), artifacts)
    except PredictionFeatureError as exc:
        assert "missing" in str(exc)
        assert dataset.feature_columns[0] in str(exc)
    else:
        raise AssertionError("Expected missing feature error")


def test_prediction_after_reload_and_class_probability_mapping(tmp_path) -> None:
    dataset, _, ml_config = _train_artifact(tmp_path)
    config = PredictionEngineConfig(artifacts_root=ml_config.artifacts_root)
    loader = PredictionArtifactLoader(config)
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    result1 = PredictionPredictor(config).predict(_prediction_input(dataset), loader.load_artifacts(entry))
    result2 = PredictionPredictor(config).predict(_prediction_input(dataset), loader.load_artifacts(entry))

    assert result1.predicted_class == result2.predicted_class
    assert result1.probability_stop_loss == result2.probability_stop_loss
    assert result1.probability_neutral == result2.probability_neutral
    assert result1.probability_take_profit == result2.probability_take_profit
    assert result1.predicted_class in {-1, 0, 1}
    assert abs(
        result1.probability_stop_loss + result1.probability_neutral + result1.probability_take_profit - 1.0
    ) < 1e-9


def test_decision_buy_candidate_hold_and_avoid() -> None:
    config = PredictionEngineConfig(take_profit_threshold=0.60, stop_loss_threshold=0.60)

    assert decide(PredictionProbabilities(0.10, 0.20, 0.70), config) == BUY_CANDIDATE
    assert decide(PredictionProbabilities(0.20, 0.50, 0.30), config) == HOLD
    assert decide(PredictionProbabilities(0.70, 0.10, 0.20), config) == AVOID
    assert confidence_level(0.10) == LOW
    assert confidence_level(0.55) == MEDIUM
    assert confidence_level(0.70) == HIGH
    assert confidence_level(0.85) == VERY_HIGH


def test_target_leakage_columns_are_rejected(tmp_path) -> None:
    dataset, _, ml_config = _train_artifact(tmp_path)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    artifacts = loader.load_artifacts(loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name))
    features = {column: dataset.frame.iloc[-1][column] for column in dataset.feature_columns}
    features["target_class"] = 1

    try:
        PredictionPredictor().predict(_prediction_input(dataset, features=features), artifacts)
    except PredictionFeatureError as exc:
        assert "Target leakage" in str(exc)
        assert "target_class" in str(exc)
    else:
        raise AssertionError("Expected target leakage rejection")


def test_pipeline_uses_only_latest_candle_and_is_idempotent_by_candle_model(tmp_path, monkeypatch) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    config = PredictionEngineConfig(artifacts_root=ml_config.artifacts_root, output_root=tmp_path / "predictions")
    older = _prediction_input(dataset, index=-2)
    latest_features = {column: dataset.frame.iloc[-1][column] for column in dataset.feature_columns}
    latest_features["supertrend_10_3_0"] = 1.0
    latest = _prediction_input(dataset, index=-1, features=latest_features)
    repository = FakePredictionRepository([latest, older])
    monkeypatch.setattr("backend.trading.prediction_engine.pipeline.get_settings", _paper_settings)

    engine = PredictionEngine(repository, config=config)
    result1 = engine.predict_latest(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)
    result2 = engine.predict_latest(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    assert result1.candle_id == latest.candle_id
    assert result2.candle_id == latest.candle_id
    assert result1.report_path == result2.report_path
    assert result1.model_name == report.best_model_name
    assert result1.report_path is not None
    assert result1.report_path.exists()
    assert result1.prediction_id == result2.prediction_id
    assert result1.prediction_engine_version == "v2"
    assert result1.feature_version == "v2"
    assert result1.confidence_level in {LOW, MEDIUM, HIGH, VERY_HIGH}
    assert result1.position_size is None
    report_payload = json.loads(result1.report_path.read_text(encoding="utf-8"))
    assert report_payload["prediction_id"] == result1.prediction_id
    assert report_payload["probability_distribution"]
    assert report_payload["loaded_manifest"]["model_name"] == report.best_model_name
    assert report_payload["reason"]["ignored_extra_features"] == ["supertrend_10_3_0"]
    assert len(list((tmp_path / "predictions").rglob("*.json"))) == 1


def test_paper_only_is_required(tmp_path, monkeypatch) -> None:
    dataset, _, ml_config = _train_artifact(tmp_path)
    config = PredictionEngineConfig(artifacts_root=ml_config.artifacts_root, output_root=tmp_path / "predictions")
    repository = FakePredictionRepository([_prediction_input(dataset)])
    monkeypatch.setattr(
        "backend.trading.prediction_engine.pipeline.get_settings",
        lambda: SimpleNamespace(trading_mode="LIVE_RESEARCH", trading_interval="5m"),
    )

    try:
        PredictionEngine(repository, config=config).predict_latest(
            symbol="BTCUSDT",
            interval="5m",
            target_name=dataset.target_name,
        )
    except RuntimeError as exc:
        assert "PAPER_ONLY" in str(exc)
    else:
        raise AssertionError("Prediction Engine V2 must reject non PAPER_ONLY mode")


def test_repository_latest_feature_query_does_not_join_targets() -> None:
    source = PredictionEngine.__module__
    assert source == "backend.trading.prediction_engine.pipeline"
    repository_source = __import__("inspect").getsource(
        __import__("backend.trading.prediction_engine.repository", fromlist=["PredictionRepository"]).PredictionRepository.load_latest_features
    )
    assert "crypto_targets" not in repository_source
    assert "ORDER BY c.open_time DESC" in repository_source


def test_sklearn_version_incompatibility_raises_compatibility_error(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    metadata_path = report.best_model_path / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["sklearn_version"] = "0.0.invalid"
    write_json(metadata_path, metadata)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionCompatibilityError as exc:
        assert exc.dependency == "sklearn"
        assert exc.expected == "0.0.invalid"
        assert exc.found == sklearn.__version__
        assert report.best_model_name in str(exc)
    else:
        raise AssertionError("Expected sklearn compatibility error")


def test_xgboost_version_incompatibility_raises_compatibility_error(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    metadata_path = report.best_model_path / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["xgboost_version"] = "0.0.invalid"
    write_json(metadata_path, metadata)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionCompatibilityError as exc:
        assert exc.dependency == "xgboost"
        assert exc.expected == "0.0.invalid"
        assert report.best_model_name in str(exc)
    else:
        raise AssertionError("Expected xgboost compatibility error")


def test_invalid_metadata_and_corrupted_manifest_raise_clear_errors(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    (report.best_model_path / "metadata.json").write_text("{not json", encoding="utf-8")
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionArtifactError as exc:
        assert "Invalid JSON" in str(exc)
        assert "metadata.json" in str(exc)
    else:
        raise AssertionError("Expected invalid metadata error")

    (ml_config.artifacts_root / "manifest.json").write_text("{not json", encoding="utf-8")
    try:
        loader.load_manifest()
    except PredictionArtifactError as exc:
        assert "Invalid JSON" in str(exc)
        assert "manifest.json" in str(exc)
    else:
        raise AssertionError("Expected corrupted manifest error")


def test_checksum_invalid_raises_artifact_error(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    metadata_path = report.best_model_path / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["checksums"] = {"feature_columns.json": "bad-checksum"}
    write_json(metadata_path, metadata)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionArtifactError as exc:
        assert "Checksum mismatch" in str(exc)
        assert "feature_columns.json" in str(exc)
    else:
        raise AssertionError("Expected checksum mismatch error")


def test_checksum_valid_is_accepted(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    feature_columns_path = report.best_model_path / "feature_columns.json"
    metadata_path = report.best_model_path / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["checksums"] = {"feature_columns.json": hashlib.sha256(feature_columns_path.read_bytes()).hexdigest()}
    write_json(metadata_path, metadata)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    assert loader.load_artifacts(entry).metadata["checksums"]


def test_nan_infinity_are_rejected_and_extra_columns_are_ignored(tmp_path) -> None:
    dataset, _, ml_config = _train_artifact(tmp_path)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    artifacts = loader.load_artifacts(loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name))
    base = {column: dataset.frame.iloc[-1][column] for column in dataset.feature_columns}

    for bad_value, expected in ((float("nan"), "nan"), (float("inf"), "infinite")):
        features = dict(base)
        features[dataset.feature_columns[0]] = bad_value
        try:
            PredictionPredictor().predict(_prediction_input(dataset, features=features), artifacts)
        except PredictionFeatureError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"Expected {expected} feature error")

    features = dict(base)
    features["extra_feature"] = 1.0
    predictor = PredictionPredictor()
    baseline = predictor.predict(_prediction_input(dataset, features=base), artifacts)
    with_extra = predictor.predict(_prediction_input(dataset, features=features), artifacts)

    assert with_extra.reason["ignored_extra_features"] == ["extra_feature"]
    assert with_extra.predicted_class == baseline.predicted_class
    assert with_extra.probability_stop_loss == baseline.probability_stop_loss
    assert with_extra.probability_neutral == baseline.probability_neutral
    assert with_extra.probability_take_profit == baseline.probability_take_profit
    assert artifacts.feature_columns == tuple(artifacts.preprocessing.feature_columns)


def test_version_mismatch_errors_are_clear(tmp_path) -> None:
    dataset, report, ml_config = _train_artifact(tmp_path)
    metadata_path = report.best_model_path / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["target_version"] = "v1"
    write_json(metadata_path, metadata)
    loader = PredictionArtifactLoader(PredictionEngineConfig(artifacts_root=ml_config.artifacts_root))
    entry = loader.select_best_model(symbol="BTCUSDT", interval="5m", target_name=dataset.target_name)

    try:
        loader.load_artifacts(entry)
    except PredictionArtifactError as exc:
        assert "target_version" in str(exc)
        assert "v2" in str(exc)
    else:
        raise AssertionError("Expected target_version mismatch")

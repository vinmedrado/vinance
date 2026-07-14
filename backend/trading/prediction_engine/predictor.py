from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd

from backend.trading.ml_engine.config import PROHIBITED_FEATURE_COLUMNS

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .decision import confidence_level, decide
from .errors import PredictionFeatureError
from .models import LoadedArtifacts, PredictionInput, PredictionProbabilities, PredictionResult


CLASS_STOP_LOSS = -1
CLASS_NEUTRAL = 0
CLASS_TAKE_PROFIT = 1


class PredictionPredictor:
    def __init__(self, config: PredictionEngineConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def predict(self, prediction_input: PredictionInput, artifacts: LoadedArtifacts) -> PredictionResult:
        ignored_extra_features = self._validate_feature_contract(prediction_input.features, artifacts.feature_columns)
        frame = pd.DataFrame([{column: prediction_input.features[column] for column in artifacts.feature_columns}])
        transformed = artifacts.preprocessing.transform(frame)
        predicted_class = int(artifacts.model.predict(transformed)[0])
        probabilities = self._predict_probabilities(artifacts.model, transformed)
        decision = decide(probabilities, self.config)
        model_version = str(artifacts.metadata.get("model_version") or artifacts.metadata.get("ml_engine_version"))
        prediction_engine_version = self.config.prediction_engine_version
        prediction_id = _prediction_id(
            symbol=prediction_input.symbol,
            interval=prediction_input.interval,
            target_name=artifacts.entry.target_name,
            model_name=artifacts.entry.model_name,
            candle_id=prediction_input.candle_id,
            model_version=model_version,
            engine_version=prediction_engine_version,
        )
        return PredictionResult(
            prediction_id=prediction_id,
            symbol=prediction_input.symbol,
            interval=prediction_input.interval,
            target_name=artifacts.entry.target_name,
            candle_id=prediction_input.candle_id,
            open_time=prediction_input.open_time,
            model_name=artifacts.entry.model_name,
            artifact_dir=artifacts.entry.artifact_dir,
            predicted_class=predicted_class,
            probability_stop_loss=probabilities.probability_stop_loss,
            probability_neutral=probabilities.probability_neutral,
            probability_take_profit=probabilities.probability_take_profit,
            confidence=probabilities.confidence,
            confidence_level=confidence_level(probabilities.confidence),
            decision=decision,
            prediction_engine_version=prediction_engine_version,
            model_version=model_version,
            feature_version=self.config.feature_version,
            risk_score=probabilities.probability_stop_loss,
            expected_return=probabilities.probability_take_profit - probabilities.probability_stop_loss,
            expected_drawdown=probabilities.probability_stop_loss,
            position_size=None,
            loaded_manifest=artifacts.entry.metadata,
            reason={
                "paper_only": True,
                "feature_version": self.config.feature_version,
                "ml_engine_version": artifacts.entry.ml_engine_version,
                "artifact_generated_at": artifacts.entry.generated_at,
                "take_profit_threshold": self.config.take_profit_threshold,
                "stop_loss_threshold": self.config.stop_loss_threshold,
                "decision_reason": _decision_reason(decision, probabilities, self.config),
                "ignored_extra_features": ignored_extra_features,
            },
        )

    def _validate_feature_contract(self, features: dict[str, Any], feature_columns: tuple[str, ...]) -> list[str]:
        leaked = sorted(set(features).intersection(PROHIBITED_FEATURE_COLUMNS))
        if leaked:
            raise PredictionFeatureError(f"Target leakage columns are not allowed for inference: {leaked}")
        expected = set(feature_columns)
        actual = set(features)
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        if missing:
            raise PredictionFeatureError(f"Feature columns mismatch. missing={missing} extra={extra}")
        invalid: list[str] = []
        nan_columns: list[str] = []
        infinite_columns: list[str] = []
        for column in feature_columns:
            value = features[column]
            numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(numeric):
                if _is_nan_like(value):
                    nan_columns.append(column)
                else:
                    invalid.append(column)
                continue
            if not math.isfinite(float(numeric)):
                infinite_columns.append(column)
        if invalid or nan_columns or infinite_columns:
            raise PredictionFeatureError(
                "Invalid feature values before preprocessing. "
                f"invalid_types={invalid} nan={nan_columns} infinite={infinite_columns}"
            )
        return extra

    def _predict_probabilities(self, model: Any, transformed: pd.DataFrame) -> PredictionProbabilities:
        if not hasattr(model, "predict_proba"):
            predicted_class = int(model.predict(transformed)[0])
            return PredictionProbabilities(
                probability_stop_loss=1.0 if predicted_class == CLASS_STOP_LOSS else 0.0,
                probability_neutral=1.0 if predicted_class == CLASS_NEUTRAL else 0.0,
                probability_take_profit=1.0 if predicted_class == CLASS_TAKE_PROFIT else 0.0,
            )

        raw = model.predict_proba(transformed)
        if raw is None or len(raw) != 1:
            raise ValueError("Model returned invalid probability output")
        classes = getattr(model, "classes_", None)
        if classes is None and hasattr(model, "estimator"):
            classes = getattr(model.estimator, "classes_", None)
        if classes is None:
            classes = np.array([CLASS_STOP_LOSS, CLASS_NEUTRAL, CLASS_TAKE_PROFIT])
        by_class = {int(label): float(probability) for label, probability in zip(classes, raw[0])}
        return PredictionProbabilities(
            probability_stop_loss=by_class.get(CLASS_STOP_LOSS, 0.0),
            probability_neutral=by_class.get(CLASS_NEUTRAL, 0.0),
            probability_take_profit=by_class.get(CLASS_TAKE_PROFIT, 0.0),
        )


def _is_nan_like(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def _prediction_id(
    *,
    symbol: str,
    interval: str,
    target_name: str,
    model_name: str,
    candle_id: int,
    model_version: str,
    engine_version: str,
) -> str:
    raw = f"{symbol}|{interval}|{target_name}|{model_name}|{candle_id}|{model_version}|{engine_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _decision_reason(
    decision: str,
    probabilities: PredictionProbabilities,
    config: PredictionEngineConfig,
) -> str:
    if decision == "AVOID":
        return f"probability_stop_loss >= {config.stop_loss_threshold}"
    if decision == "BUY_CANDIDATE":
        return f"probability_take_profit >= {config.take_profit_threshold}"
    return "no probability threshold reached"

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .models import PredictionResult


class PredictionReportWriter:
    def __init__(self, config: PredictionEngineConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def write(self, result: PredictionResult) -> PredictionResult:
        path = self.report_path(result)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_report_dict(result), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return replace(result, report_path=path)

    def report_path(self, result: PredictionResult) -> Path:
        safe_target = result.target_name.replace("/", "_")
        safe_model = result.model_name.replace("/", "_")
        return self.config.output_root / result.symbol / result.interval / safe_target / f"{safe_model}_{result.candle_id}.json"


def to_report_dict(result: PredictionResult) -> dict[str, Any]:
    probability_distribution = {
        "-1": result.probability_stop_loss,
        "0": result.probability_neutral,
        "1": result.probability_take_profit,
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": result.prediction_engine_version,
        "prediction_id": result.prediction_id,
        "symbol": result.symbol,
        "interval": result.interval,
        "target_name": result.target_name,
        "candle_id": result.candle_id,
        "open_time": result.open_time.isoformat(),
        "model_name": result.model_name,
        "model_version": result.model_version,
        "feature_version": result.feature_version,
        "artifact_dir": str(result.artifact_dir),
        "predicted_class": result.predicted_class,
        "probability_stop_loss": result.probability_stop_loss,
        "probability_neutral": result.probability_neutral,
        "probability_take_profit": result.probability_take_profit,
        "probability_distribution": probability_distribution,
        "confidence": result.confidence,
        "confidence_level": result.confidence_level,
        "decision": result.decision,
        "decision_reason": result.reason.get("decision_reason"),
        "risk_score": result.risk_score,
        "expected_return": result.expected_return,
        "expected_drawdown": result.expected_drawdown,
        "position_size": result.position_size,
        "loaded_manifest": result.loaded_manifest,
        "reason": result.reason,
    }

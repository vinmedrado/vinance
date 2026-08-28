from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import ValidationResult


class ValidationReportWriter:
    def write(self, result: ValidationResult, *, overwrite: bool) -> dict[str, Path]:
        result.output_dir.mkdir(parents=True, exist_ok=True)
        payloads = {
            "validation_summary": {
                "validation_run_id": result.run_id,
                "overall_score": result.overall_score,
                "classification": result.classification,
                "robustness_consolidated": result.temporal_robustness,
                "paper_trading_ready": result.readiness["paper_trading_ready"],
                "paper_trading_continuous_ready": result.readiness["paper_trading_continuous_ready"],
                "live_trading_ready": False,
            },
            "campaign_coverage": result.coverage,
            "case_results": result.case_results,
            "cross_validation": result.cross_validation,
            "temporal_robustness": result.temporal_robustness,
            "asset_ranking": result.asset_ranking,
            "target_ranking": result.target_ranking,
            "model_ranking": result.model_ranking,
            "readiness": result.readiness,
            "run_metadata": result.metadata,
        }
        paths: dict[str, Path] = {}
        for name, payload in payloads.items():
            path = result.output_dir / f"{name}.json"
            if path.exists() and not overwrite:
                raise FileExistsError(f"Validation report already exists and overwrite=False: {path}")
            path.write_text(
                json.dumps(_sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            paths[name] = path
        return paths


def _sanitize(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value

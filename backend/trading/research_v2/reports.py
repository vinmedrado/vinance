from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import ResearchResult


class ResearchReportWriter:
    def write(self, result: ResearchResult, *, overwrite: bool) -> dict[str, Path]:
        result.output_dir.mkdir(parents=True, exist_ok=True)
        payloads = {
            "research_summary": {
                "research_run_id": result.run_id,
                "source_backtest_run_id": result.source_run_id,
                "robustness_score": result.robustness["robustness_score"],
                "robustness_classification": result.robustness["classification"],
                "recommended_tp_threshold": result.recommendation["recommended_tp_threshold"],
                "recommended_sl_threshold": result.recommendation["recommended_sl_threshold"],
                "confidence_score": result.recommendation["confidence_score"],
                "ready_for_paper_trading": result.recommendation["ready_for_paper_trading"],
                "ready_for_live_trading": False,
            },
            "threshold_analysis": result.threshold_analysis,
            "robustness_analysis": result.robustness,
            "sensitivity_analysis": result.sensitivity,
            "monte_carlo": result.monte_carlo,
            "bootstrap": result.bootstrap,
            "stability_heatmaps": result.heatmaps,
            "threshold_ranking": result.ranking,
            "recommendation": result.recommendation,
            "run_metadata": result.metadata,
        }
        paths: dict[str, Path] = {}
        for name, payload in payloads.items():
            path = result.output_dir / f"{name}.json"
            if path.exists() and not overwrite:
                raise FileExistsError(f"Research report already exists and overwrite=False: {path}")
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

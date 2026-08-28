from __future__ import annotations

import hashlib
import json
from typing import Any

from .analyzer import analyze_case, consolidate_temporal, cross_validation_summary
from .config import ValidationConfig
from .models import ValidationInputs, ValidationResult
from .reports import ValidationReportWriter
from .repository import ValidationRepository
from .scoring import campaign_score, rank_dimension, readiness, score_case


class ValidationCampaign:
    def __init__(self, config: ValidationConfig, repository: ValidationRepository | None = None) -> None:
        self.config = config
        self.repository = repository or ValidationRepository(config)

    def run(self, inputs: ValidationInputs | None = None) -> ValidationResult:
        source = inputs or self.repository.load()
        case_results = [score_case(analyze_case(case)) for case in source.cases]
        temporal = consolidate_temporal(case_results)
        cross_validation = cross_validation_summary(case_results)
        campaign = campaign_score(case_results, source.coverage, self.config)
        campaign_readiness = readiness(case_results, source.coverage, temporal, campaign, self.config)
        asset_ranking = rank_dimension(case_results, "symbol")
        target_ranking = rank_dimension(case_results, "target_name")
        model_ranking = rank_dimension(case_results, "model_name")
        run_id = _validation_run_id(source, self.config)
        metadata = {
            "engine_version": self.config.engine_version,
            "validation_run_id": run_id,
            "manifest_generated_at": source.manifest_generated_at,
            "source_backtest_run_ids": sorted(case.source_backtest_run_id for case in source.cases),
            "source_research_run_ids": sorted(case.source_research_run_id for case in source.cases),
            "paper_only": True,
            "performs_trading": False,
            "performs_inference": False,
            "trains_models": False,
            "alters_thresholds": False,
            "strategy_quality_score": campaign["strategy_quality_score"],
            "coverage_score": campaign["coverage_score"],
            "coverage_components": campaign["coverage_components"],
            "coverage_multiplier": campaign["coverage_multiplier"],
            "overall_formula": campaign["overall_formula"],
        }
        result = ValidationResult(
            run_id=run_id,
            output_dir=self.config.output_root / run_id,
            overall_score=campaign["overall_score"],
            classification=campaign["classification"],
            coverage=source.coverage,
            case_results=case_results,
            cross_validation=cross_validation,
            temporal_robustness=temporal,
            asset_ranking=asset_ranking,
            target_ranking=target_ranking,
            model_ranking=model_ranking,
            readiness=campaign_readiness,
            metadata=metadata,
        )
        result.reports = ValidationReportWriter().write(result, overwrite=self.config.overwrite)
        return result


def _validation_run_id(source: ValidationInputs, config: ValidationConfig) -> str:
    payload: dict[str, Any] = {
        "manifest_generated_at": source.manifest_generated_at,
        "backtest_runs": sorted(case.source_backtest_run_id for case in source.cases),
        "research_runs": sorted(case.source_research_run_id for case in source.cases),
        "artifacts": sorted(artifact.key for artifact in source.artifacts),
        "config": config.deterministic_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]

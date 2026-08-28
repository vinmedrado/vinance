from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ValidationConfig
from .models import ArtifactCandidate, ValidationCase, ValidationInputs


BACKTEST_FILES = ("backtest_summary", "walk_forward_results", "monthly_results", "run_metadata")
RESEARCH_FILES = (
    "research_summary",
    "robustness_analysis",
    "monte_carlo",
    "bootstrap",
    "recommendation",
    "run_metadata",
)


class ValidationRepository:
    """Discovers report-backed validation cases without loading model artifacts."""

    def __init__(self, config: ValidationConfig) -> None:
        self.config = config

    def load(self) -> ValidationInputs:
        manifest = self._read(self.config.manifest_path)
        artifacts = tuple(self._artifact_candidates(manifest))
        research_by_backtest = self._research_runs()
        cases: list[ValidationCase] = []
        unmatched_backtests: list[str] = []
        invalid_backtests: list[str] = []
        artifact_keys = {artifact.key for artifact in artifacts}

        for run_dir in self._run_dirs(self.config.backtesting_output_root):
            metadata_path = run_dir / "run_metadata.json"
            metadata = self._read(metadata_path)
            run_id = str(metadata.get("run_id") or run_dir.name)
            if metadata.get("temporal_integrity_valid") is not True:
                invalid_backtests.append(run_id)
                continue
            key = (
                str(metadata.get("symbol")),
                str(metadata.get("interval")),
                str(metadata.get("target_name")),
                _normalize_model(str(metadata.get("model_name"))),
            )
            if key not in artifact_keys:
                unmatched_backtests.append(run_id)
                continue
            research_dir = research_by_backtest.get(run_id)
            if research_dir is None:
                unmatched_backtests.append(run_id)
                continue
            cases.append(self._load_case(run_dir, research_dir, metadata))

        cases.sort(key=lambda case: (case.symbol, case.target_name, case.model_name, case.period_start, case.source_backtest_run_id))
        covered_keys = {case.combination_key for case in cases}
        missing_artifacts = [
            {
                "symbol": artifact.symbol,
                "interval": artifact.interval,
                "target_name": artifact.target_name,
                "model_name": artifact.model_name,
                "reason": "no paired valid Backtesting V2 and Research V2 reports",
            }
            for artifact in artifacts
            if artifact.key not in covered_keys
        ]
        coverage = _coverage(self.config, artifacts, cases, missing_artifacts, unmatched_backtests, invalid_backtests)
        return ValidationInputs(
            manifest_generated_at=manifest.get("generated_at"),
            artifacts=artifacts,
            cases=tuple(cases),
            coverage=coverage,
        )

    def _artifact_candidates(self, manifest: dict[str, Any]) -> list[ArtifactCandidate]:
        candidates = []
        for row in manifest.get("models", []):
            symbol = str(row.get("symbol"))
            model = _normalize_model(str(row.get("model_name")))
            if symbol not in self.config.assets or model not in self.config.supported_models:
                continue
            candidates.append(
                ArtifactCandidate(
                    symbol=symbol,
                    interval=str(row.get("interval")),
                    target_name=str(row.get("target_name")),
                    model_name=model,
                    artifact_dir=str(row.get("artifact_dir", "")),
                    is_best=bool(row.get("is_best", False)),
                )
            )
        return candidates

    def _research_runs(self) -> dict[str, Path]:
        selected: dict[str, tuple[str, Path]] = {}
        for run_dir in self._run_dirs(self.config.research_output_root):
            metadata = self._read(run_dir / "run_metadata.json")
            source_id = str(metadata.get("source_backtest_run_id") or "")
            if not source_id:
                continue
            timestamp = str(metadata.get("source_timestamp") or "")
            if source_id not in selected or timestamp > selected[source_id][0]:
                selected[source_id] = (timestamp, run_dir)
        return {source_id: item[1] for source_id, item in selected.items()}

    def _load_case(self, backtest_dir: Path, research_dir: Path, metadata: dict[str, Any]) -> ValidationCase:
        backtest = {name: self._read(backtest_dir / f"{name}.json") for name in BACKTEST_FILES if name != "run_metadata"}
        research = {name: self._read(research_dir / f"{name}.json") for name in RESEARCH_FILES}
        research_metadata = research["run_metadata"]
        source_id = str(metadata.get("run_id") or backtest_dir.name)
        if str(research_metadata.get("source_backtest_run_id")) != source_id:
            raise ValueError(f"Research report does not reference backtest {source_id}")
        return ValidationCase(
            source_backtest_run_id=source_id,
            source_research_run_id=str(research_metadata.get("research_run_id") or research_dir.name),
            backtest_dir=backtest_dir,
            research_dir=research_dir,
            symbol=str(metadata["symbol"]),
            interval=str(metadata["interval"]),
            target_name=str(metadata["target_name"]),
            model_name=_normalize_model(str(metadata["model_name"])),
            period_start=str(metadata.get("period_start", "")),
            period_end=str(metadata.get("period_end", "")),
            backtest_summary=backtest["backtest_summary"],
            walk_forward=backtest["walk_forward_results"],
            monthly_results=backtest["monthly_results"],
            research_summary=research["research_summary"],
            robustness=research["robustness_analysis"],
            monte_carlo=research["monte_carlo"],
            bootstrap=research["bootstrap"],
            recommendation=research["recommendation"],
        )

    @staticmethod
    def _run_dirs(root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(path for path in root.iterdir() if path.is_dir() and (path / "run_metadata.json").is_file())

    @staticmethod
    def _read(path: Path) -> Any:
        if not path.is_file():
            raise FileNotFoundError(f"Required validation input is missing: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON input: {path}") from exc


def _coverage(
    config: ValidationConfig,
    artifacts: tuple[ArtifactCandidate, ...],
    cases: list[ValidationCase],
    missing_artifacts: list[dict[str, Any]],
    unmatched_backtests: list[str],
    invalid_backtests: list[str],
) -> dict[str, Any]:
    artifact_assets = sorted({item.symbol for item in artifacts})
    artifact_targets = sorted({item.target_name for item in artifacts})
    artifact_models = sorted({item.model_name for item in artifacts})
    validated_assets = sorted({item.symbol for item in cases})
    validated_targets = sorted({item.target_name for item in cases})
    validated_models = sorted({item.model_name for item in cases})
    periods = sorted({(item.period_start, item.period_end) for item in cases})
    return {
        "requested_assets": list(config.assets),
        "supported_model_families": list(config.supported_models),
        "artifact_assets": artifact_assets,
        "artifact_targets": artifact_targets,
        "artifact_models": artifact_models,
        "validated_assets": validated_assets,
        "validated_targets": validated_targets,
        "validated_models": validated_models,
        "validated_periods": [{"start": start, "end": end} for start, end in periods],
        "artifact_combinations": len(artifacts),
        "validated_cases": len(cases),
        "validated_combinations": len({case.combination_key for case in cases}),
        "missing_artifact_reports": missing_artifacts,
        "unmatched_backtest_runs": sorted(unmatched_backtests),
        "invalid_temporal_backtest_runs": sorted(invalid_backtests),
    }


def _normalize_model(value: str) -> str:
    aliases = {
        "histgradientboosting": "hist_gradient_boosting",
        "histgradientboostingclassifier": "hist_gradient_boosting",
        "randomforest": "random_forest",
        "randomforestclassifier": "random_forest",
        "extratrees": "extra_trees",
        "extratreesclassifier": "extra_trees",
        "logisticregression": "logistic_regression",
        "xgbclassifier": "xgboost",
    }
    compact = value.lower().replace("_", "").replace("-", "").replace(" ", "")
    return aliases.get(compact, value.lower())

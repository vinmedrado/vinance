from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactCandidate:
    symbol: str
    interval: str
    target_name: str
    model_name: str
    artifact_dir: str
    is_best: bool

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.symbol, self.interval, self.target_name, self.model_name


@dataclass(frozen=True)
class ValidationCase:
    source_backtest_run_id: str
    source_research_run_id: str
    backtest_dir: Path
    research_dir: Path
    symbol: str
    interval: str
    target_name: str
    model_name: str
    period_start: str
    period_end: str
    backtest_summary: dict[str, Any]
    walk_forward: dict[str, Any]
    monthly_results: list[dict[str, Any]]
    research_summary: dict[str, Any]
    robustness: dict[str, Any]
    monte_carlo: dict[str, Any]
    bootstrap: dict[str, Any]
    recommendation: dict[str, Any]

    @property
    def combination_key(self) -> tuple[str, str, str, str]:
        return self.symbol, self.interval, self.target_name, self.model_name


@dataclass(frozen=True)
class ValidationInputs:
    manifest_generated_at: str | None
    artifacts: tuple[ArtifactCandidate, ...]
    cases: tuple[ValidationCase, ...]
    coverage: dict[str, Any]


@dataclass
class ValidationResult:
    run_id: str
    output_dir: Path
    overall_score: float
    classification: str
    coverage: dict[str, Any]
    case_results: list[dict[str, Any]]
    cross_validation: dict[str, Any]
    temporal_robustness: dict[str, Any]
    asset_ranking: list[dict[str, Any]]
    target_ranking: list[dict[str, Any]]
    model_ranking: list[dict[str, Any]]
    readiness: dict[str, Any]
    metadata: dict[str, Any]
    reports: dict[str, Path] = field(default_factory=dict)

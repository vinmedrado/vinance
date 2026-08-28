from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BacktestReports:
    run_id: str
    run_dir: Path
    summary: dict[str, Any]
    trades: list[dict[str, Any]]
    equity_curve: list[dict[str, Any]]
    drawdown_curve: list[dict[str, Any]]
    daily_results: list[dict[str, Any]]
    monthly_results: list[dict[str, Any]]
    signal_analysis: dict[str, Any]
    threshold_comparison: list[dict[str, Any]]
    baseline_comparison: list[dict[str, Any]]
    walk_forward_results: dict[str, Any]
    run_metadata: dict[str, Any]


@dataclass
class ResearchResult:
    run_id: str
    source_run_id: str
    output_dir: Path
    threshold_analysis: dict[str, Any]
    robustness: dict[str, Any]
    sensitivity: dict[str, Any]
    monte_carlo: dict[str, Any]
    bootstrap: dict[str, Any]
    heatmaps: dict[str, Any]
    ranking: list[dict[str, Any]]
    recommendation: dict[str, Any]
    metadata: dict[str, Any]
    reports: dict[str, Path] = field(default_factory=dict)

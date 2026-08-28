from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ResearchConfig
from .models import BacktestReports


REPORT_NAMES = (
    "backtest_summary",
    "trades",
    "equity_curve",
    "drawdown_curve",
    "daily_results",
    "monthly_results",
    "signal_analysis",
    "threshold_comparison",
    "baseline_comparison",
    "walk_forward_results",
    "run_metadata",
)


class ResearchRepository:
    """Loads immutable Backtesting V2 report bundles from disk."""

    def __init__(self, config: ResearchConfig) -> None:
        self.config = config

    def load_latest(self) -> BacktestReports:
        run_dir = self._resolve_run_dir()
        payloads = {name: self._read(run_dir / f"{name}.json") for name in REPORT_NAMES}
        metadata = payloads["run_metadata"]
        run_id = str(metadata.get("run_id") or run_dir.name)
        if run_id != run_dir.name:
            raise ValueError(f"Backtest run_id mismatch: directory={run_dir.name}, metadata={run_id}")
        if metadata.get("engine_version") != "v2":
            raise ValueError("Research V2 only accepts Backtesting Engine V2 reports")
        if metadata.get("temporal_integrity_valid") is not True:
            raise ValueError("Backtest temporal integrity must be valid before research")
        return BacktestReports(
            run_id=run_id,
            run_dir=run_dir,
            summary=payloads["backtest_summary"],
            trades=payloads["trades"],
            equity_curve=payloads["equity_curve"],
            drawdown_curve=payloads["drawdown_curve"],
            daily_results=payloads["daily_results"],
            monthly_results=payloads["monthly_results"],
            signal_analysis=payloads["signal_analysis"],
            threshold_comparison=payloads["threshold_comparison"],
            baseline_comparison=payloads["baseline_comparison"],
            walk_forward_results=payloads["walk_forward_results"],
            run_metadata=metadata,
        )

    def _resolve_run_dir(self) -> Path:
        root = self.config.backtesting_output_root
        if self.config.backtest_run_id:
            candidate = root / self.config.backtest_run_id
            if not candidate.is_dir():
                raise FileNotFoundError(f"Backtest run not found: {candidate}")
            return candidate
        if not root.is_dir():
            raise FileNotFoundError(f"Backtesting V2 output root not found: {root}")
        candidates = [path for path in root.iterdir() if path.is_dir()]
        valid = [path for path in candidates if (path / "run_metadata.json").is_file()]
        if not valid:
            raise FileNotFoundError(f"No Backtesting V2 report runs found in {root}")
        return max(valid, key=self._run_timestamp)

    @staticmethod
    def _run_timestamp(run_dir: Path) -> tuple[datetime, float]:
        try:
            metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            value = str(metadata.get("timestamp") or "")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            parsed = datetime.min
        return parsed.replace(tzinfo=None), run_dir.stat().st_mtime

    @staticmethod
    def _read(path: Path) -> Any:
        if not path.is_file():
            raise FileNotFoundError(f"Required Backtesting V2 report is missing: {path.name}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON report: {path}") from exc

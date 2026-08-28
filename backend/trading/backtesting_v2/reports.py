from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from backend.trading.paper_trading_v2.reports import snapshot_to_dict, trade_to_dict
from backend.trading.prediction_engine.models import PredictionResult

from .config import BacktestingConfig
from .models import BacktestResult


class BacktestingReportWriter:
    def __init__(self, config: BacktestingConfig) -> None:
        self.config = config

    def write_run(self, result: BacktestResult, *, overwrite: bool) -> dict[str, Path]:
        output_dir = result.context.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payloads: dict[str, Any] = {
            "backtest_summary": result.metrics,
            "trades": [trade_to_dict(trade) for trade in result.trades],
            "equity_curve": [snapshot_to_dict(snapshot) for snapshot in result.equity_curve],
            "drawdown_curve": result.drawdown_curve,
            "daily_results": result.daily_results,
            "monthly_results": result.monthly_results,
            "signal_analysis": result.signal_analysis,
            "threshold_comparison": result.threshold_comparison,
            "baseline_comparison": result.baseline_comparison,
            "walk_forward_results": result.walk_forward_results,
            "run_metadata": result.context.metadata | {"run_id": result.context.run_id},
        }
        paths: dict[str, Path] = {}
        for name, payload in payloads.items():
            path = output_dir / f"{name}.json"
            if path.exists() and not overwrite:
                raise FileExistsError(f"Report already exists and overwrite=False: {path}")
            _write_json(path, payload)
            paths[name] = path
        return paths

    def write_named(self, output_dir: Path, name: str, payload: Any, *, overwrite: bool = True) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{name}.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Report already exists and overwrite=False: {path}")
        _write_json(path, payload)
        return path


def prediction_to_dict(prediction: PredictionResult) -> dict[str, Any]:
    payload = asdict(prediction)
    payload["artifact_dir"] = str(payload["artifact_dir"])
    if payload.get("report_path") is not None:
        payload["report_path"] = str(payload["report_path"])
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

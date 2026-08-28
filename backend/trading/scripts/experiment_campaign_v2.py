from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from backend.trading.backtesting_v2.config import BacktestingConfig
from backend.trading.backtesting_v2.pipeline import run_backtest
from backend.trading.config import get_settings
from backend.trading.ml_engine.config import MLEngineConfig
from backend.trading.ml_engine.pipeline import MLEnginePipeline
from backend.trading.ml_engine.registry import model_registry
from backend.trading.ml_engine.repository import MLEngineRepository
from backend.trading.research_v2.config import ResearchConfig
from backend.trading.research_v2.pipeline import run_research
from backend.trading.storage.database import create_sync_engine
from backend.trading.validation_v2.config import ValidationConfig
from backend.trading.validation_v2.pipeline import run_validation


ASSETS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")
MODELS = (
    "logistic_regression",
    "random_forest",
    "extra_trees",
    "hist_gradient_boosting",
    "xgboost",
)
INTERVAL = "5m"
SEED = 42
OUTPUT_ROOT = Path("backend/trading/output/experiment_campaign_v2")
ARTIFACTS_ROOT = Path("backend/trading/artifacts/ml_engine_v2")
BACKTEST_ROOT = Path("backend/trading/output/backtesting_v2")
RESEARCH_ROOT = Path("backend/trading/output/research_v2")
VALIDATION_ROOT = Path("backend/trading/output/validation_v2")


class ExperimentCampaign:
    def __init__(self, *, phase: str, retry_failed: bool = False) -> None:
        if phase not in {"pilot", "full"}:
            raise ValueError("phase must be pilot or full")
        self.phase = phase
        self.retry_failed = retry_failed
        self.settings = get_settings()
        if self.settings.trading_mode != "PAPER_ONLY":
            raise RuntimeError("Experiment campaign requires trading_mode=PAPER_ONLY")
        self.engine = create_sync_engine(self.settings.database_url)
        self.ml_config = MLEngineConfig(artifacts_root=ARTIFACTS_ROOT, random_state=SEED)
        self.ml_pipeline = MLEnginePipeline(MLEngineRepository(self.engine), self.ml_config)
        self.available_models = set(model_registry(self.ml_config))
        self.inventory = self._discover_inventory()
        self.targets = tuple(sorted({target for row in self.inventory for target in row["targets"]}))
        if not self.targets:
            raise RuntimeError("No V2 targets found for the campaign assets")
        self.cases = self._load_or_initialize_cases()
        self._ensure_case_records()
        self.phase_started = time.perf_counter()

    def run(self) -> dict[str, Any]:
        try:
            if self.phase == "full":
                self._require_pilot_gate()
            selected = [case for case in self.cases if self._selected(case)]
            print(f"campaign phase={self.phase} selected={len(selected)} total={len(self.cases)}")
            for index, case in enumerate(selected, start=1):
                status = case["status"]
                if status in {"completed", "skipped"}:
                    print(f"[{index}/{len(selected)}] {case['case_id']} status={status}; not repeated")
                    continue
                if status == "failed" and not self.retry_failed:
                    print(f"[{index}/{len(selected)}] {case['case_id']} status=failed; use --retry-failed")
                    continue
                self._execute_case(case, index=index, total=len(selected))
            self._run_validation_checkpoint()
            return self._persist_all()
        finally:
            self.engine.dispose()

    def _execute_case(self, case: dict[str, Any], *, index: int, total: int) -> None:
        case_id = case["case_id"]
        started = time.perf_counter()
        case.update(
            status="running",
            started_at=_now(),
            finished_at=None,
            duration_seconds=None,
            error_message=None,
        )
        self._persist_all()
        log_path = OUTPUT_ROOT / "logs" / f"{case_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{index}/{total}] running {case_id}")
        try:
            with log_path.open("a", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
                print(f"\n=== {_now()} phase={self.phase} case={case_id} ===")
                if case["model_name"] not in self.available_models:
                    case["status"] = "skipped"
                    case["error_message"] = f"model unavailable in ML Engine registry: {case['model_name']}"
                    return
                report = self.ml_pipeline.train_target(
                    symbol=case["symbol"],
                    interval=case["interval"],
                    target_name=case["target_name"],
                    models=(case["model_name"],),
                )
                case["artifact_path"] = str(report.best_model_path)
                if report.best_model_name != case["model_name"]:
                    raise RuntimeError(
                        f"ML Engine trained unexpected model: {report.best_model_name} != {case['model_name']}"
                    )
                if "_short_" in case["target_name"]:
                    case["status"] = "skipped"
                    case["error_message"] = "Paper Trading V2 currently supports long targets only; artifact retained"
                    return

                backtest = run_backtest(
                    BacktestingConfig(
                        symbol=case["symbol"],
                        interval=case["interval"],
                        target_name=case["target_name"],
                        artifacts_root=self._case_artifacts_view(case),
                        output_root=BACKTEST_ROOT,
                        seed=SEED,
                        paper_only=True,
                    )
                )
                if backtest.context.model_name != case["model_name"]:
                    raise RuntimeError(
                        f"Backtesting V2 selected unexpected model: {backtest.context.model_name} != {case['model_name']}"
                    )
                case["backtest_run_id"] = backtest.context.run_id
                research = run_research(
                    ResearchConfig(
                        backtesting_output_root=BACKTEST_ROOT,
                        output_root=RESEARCH_ROOT,
                        backtest_run_id=backtest.context.run_id,
                        seed=SEED,
                        paper_only=True,
                    )
                )
                case["research_run_id"] = research.run_id
                validation = run_validation(self._validation_config())
                case["validation_run_id"] = validation.run_id
                case["status"] = "completed"
                print(
                    f"completed artifact={case['artifact_path']} backtest={case['backtest_run_id']} "
                    f"research={case['research_run_id']} validation={case['validation_run_id']}"
                )
        except Exception as exc:
            case["status"] = "failed"
            case["error_message"] = f"{type(exc).__name__}: {exc}"
            with log_path.open("a", encoding="utf-8") as log:
                traceback.print_exc(file=log)
        finally:
            case["finished_at"] = _now()
            case["duration_seconds"] = time.perf_counter() - started
            self._write_case_report(case)
            self._persist_all()
            print(
                f"[{index}/{total}] finished {case_id} status={case['status']} "
                f"seconds={case['duration_seconds']:.2f}"
            )

    def _run_validation_checkpoint(self) -> None:
        try:
            validation = run_validation(self._validation_config())
        except Exception as exc:
            print(f"validation checkpoint failed: {type(exc).__name__}: {exc}")
            return
        for case in self.cases:
            if case["status"] == "completed" and not case.get("validation_run_id"):
                case["validation_run_id"] = validation.run_id

    def _validation_config(self) -> ValidationConfig:
        return ValidationConfig(
            manifest_path=ARTIFACTS_ROOT / "manifest.json",
            backtesting_output_root=BACKTEST_ROOT,
            research_output_root=RESEARCH_ROOT,
            output_root=VALIDATION_ROOT,
            assets=ASSETS,
            paper_only=True,
        )

    def _selected(self, case: dict[str, Any]) -> bool:
        if self.phase == "full":
            return True
        return case["symbol"] == "ETHUSDT" and case["model_name"] in {
            "hist_gradient_boosting",
            "xgboost",
        }

    def _discover_inventory(self) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT
                c.symbol,
                c.interval,
                COUNT(DISTINCT c.id) AS candle_count,
                COUNT(DISTINCT f.candle_id) AS feature_count,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT t.target_name ORDER BY t.target_name), NULL) AS targets
            FROM crypto_candles c
            LEFT JOIN crypto_features f
              ON f.candle_id = c.id
             AND f.feature_version = :feature_version
            LEFT JOIN crypto_targets t
              ON t.candle_id = c.id
             AND t.target_name LIKE 'v2_%'
            WHERE c.symbol = ANY(:symbols)
              AND c.interval = :interval
            GROUP BY c.symbol, c.interval
            ORDER BY c.symbol, c.interval
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                query,
                {
                    "symbols": list(ASSETS),
                    "interval": INTERVAL,
                    "feature_version": self.ml_config.feature_version,
                },
            )
            inventory = [
                {
                    "symbol": str(row[0]),
                    "interval": str(row[1]),
                    "candle_count": int(row[2]),
                    "feature_count": int(row[3]),
                    "targets": [str(target) for target in (row[4] or [])],
                }
                for row in rows
            ]
        found_assets = {row["symbol"] for row in inventory}
        missing_assets = sorted(set(ASSETS) - found_assets)
        if missing_assets:
            raise RuntimeError(f"Campaign assets missing from crypto_candles: {missing_assets}")
        return inventory

    def _case_artifacts_view(self, case: dict[str, Any]) -> Path:
        manifest = _read_json(ARTIFACTS_ROOT / "manifest.json")
        matches = [
            row
            for row in manifest.get("models", [])
            if str(row.get("symbol")) == case["symbol"]
            and str(row.get("interval")) == case["interval"]
            and str(row.get("target_name")) == case["target_name"]
            and str(row.get("model_name")) == case["model_name"]
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one manifest entry for {case['case_id']}; found {len(matches)}"
            )
        entry = dict(matches[0])
        entry["is_best"] = True
        view_root = OUTPUT_ROOT / "artifact_views" / case["case_id"]
        _write_json(
            view_root / "manifest.json",
            {"generated_at": manifest.get("generated_at"), "models": [entry]},
        )
        return view_root

    def _require_pilot_gate(self) -> None:
        gate = _safe_json(OUTPUT_ROOT / "pilot_gate.json")
        if not gate or gate.get("passed") is not True:
            raise RuntimeError("Full campaign requires a successful pilot_gate.json")

    def _load_or_initialize_cases(self) -> list[dict[str, Any]]:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        status_path = OUTPUT_ROOT / "campaign_status.json"
        prior: dict[str, dict[str, Any]] = {}
        if status_path.exists():
            payload = _read_json(status_path)
            prior = {str(case["case_id"]): case for case in payload.get("cases", [])}
        existing = self._existing_completed_cases()
        cases = []
        for symbol in ASSETS:
            for target in self.targets:
                for model in MODELS:
                    case_id = _case_id(symbol, INTERVAL, target, model)
                    case = prior.get(case_id) or _empty_case(case_id, symbol, target, model)
                    if case_id in existing and case["status"] not in {"completed", "skipped"}:
                        case.update(existing[case_id], status="completed", error_message=None)
                    cases.append(case)
        cases.sort(key=lambda row: (row["symbol"], row["target_name"], row["model_name"]))
        baseline_path = OUTPUT_ROOT / "campaign_manifest.json"
        if baseline_path.exists():
            campaign_manifest = _read_json(baseline_path)
            campaign_manifest["inventory"] = self.inventory
            campaign_manifest["targets"] = list(self.targets)
            campaign_manifest["total_combinations"] = len(cases)
            _write_json(baseline_path, campaign_manifest)
        else:
            baseline = self._latest_validation_snapshot()
            _write_json(
                baseline_path,
                {
                    "campaign_id": _campaign_id(self.targets),
                    "created_at": _now(),
                    "paper_only": True,
                    "seed": SEED,
                    "assets": list(ASSETS),
                    "interval": INTERVAL,
                    "targets": list(self.targets),
                    "models": list(MODELS),
                    "total_combinations": len(cases),
                    "inventory": self.inventory,
                    "baseline_validation": baseline,
                    "case_ids": [case["case_id"] for case in cases],
                },
            )
        return cases

    def _existing_completed_cases(self) -> dict[str, dict[str, Any]]:
        artifacts = _manifest_artifacts()
        research_by_backtest = _research_by_backtest()
        validation_by_backtest = _validation_by_backtest()
        completed: dict[str, dict[str, Any]] = {}
        for run_dir in _run_dirs(BACKTEST_ROOT):
            metadata = _safe_json(run_dir / "run_metadata.json")
            if not metadata or metadata.get("temporal_integrity_valid") is not True:
                continue
            key = (
                str(metadata.get("symbol")),
                str(metadata.get("interval")),
                str(metadata.get("target_name")),
                str(metadata.get("model_name")),
            )
            backtest_id = str(metadata.get("run_id") or run_dir.name)
            research_id = research_by_backtest.get(backtest_id)
            validation_id = validation_by_backtest.get(backtest_id)
            artifact_path = artifacts.get(key)
            if artifact_path and research_id and validation_id:
                case_id = _case_id(*key)
                completed[case_id] = {
                    "artifact_path": artifact_path,
                    "backtest_run_id": backtest_id,
                    "research_run_id": research_id,
                    "validation_run_id": validation_id,
                    "started_at": metadata.get("timestamp"),
                    "finished_at": metadata.get("timestamp"),
                    "duration_seconds": 0.0,
                }
        return completed

    def _latest_validation_snapshot(self) -> dict[str, Any] | None:
        candidates = []
        for run_dir in _run_dirs(VALIDATION_ROOT):
            summary = _safe_json(run_dir / "validation_summary.json")
            coverage = _safe_json(run_dir / "campaign_coverage.json")
            if summary and coverage:
                candidates.append((run_dir.stat().st_mtime, run_dir.name, summary, coverage))
        if not candidates:
            return None
        _, run_id, summary, coverage = max(candidates)
        return {
            "validation_run_id": run_id,
            "overall_score": summary.get("overall_score"),
            "validated_cases": coverage.get("validated_cases"),
            "validated_assets": coverage.get("validated_assets"),
            "validated_targets": coverage.get("validated_targets"),
            "validated_models": coverage.get("validated_models"),
            "validated_periods": coverage.get("validated_periods"),
        }

    def _write_case_report(self, case: dict[str, Any]) -> None:
        path = OUTPUT_ROOT / "cases" / f"{case['case_id']}.json"
        _write_json(path, case)

    def _ensure_case_records(self) -> None:
        log_root = OUTPUT_ROOT / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        for case in self.cases:
            self._write_case_report(case)
            log_path = log_root / f"{case['case_id']}.log"
            if not log_path.exists():
                log_path.write_text(
                    f"=== {_now()} discovered case={case['case_id']} status={case['status']} ===\n",
                    encoding="utf-8",
                )

    def _persist_all(self) -> dict[str, Any]:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        completed = [case for case in self.cases if case["status"] == "completed"]
        failed = [case for case in self.cases if case["status"] == "failed"]
        skipped = [case for case in self.cases if case["status"] == "skipped"]
        pending = [case for case in self.cases if case["status"] == "pending"]
        running = [case for case in self.cases if case["status"] == "running"]
        phase_cases = [case for case in self.cases if self._selected(case)]
        latest_validation = self._latest_validation_snapshot()
        validation_details = self._latest_validation_details()
        summary = {
            "campaign_id": _campaign_id(self.targets),
            "phase": self.phase,
            "updated_at": _now(),
            "total_combinations": len(self.cases),
            "completed": len(completed),
            "failed": len(failed),
            "skipped": len(skipped),
            "pending": len(pending),
            "running": len(running),
            "phase_total": len(phase_cases),
            "phase_completed": sum(case["status"] == "completed" for case in phase_cases),
            "phase_failed": sum(case["status"] == "failed" for case in phase_cases),
            "phase_skipped": sum(case["status"] == "skipped" for case in phase_cases),
            "duration_seconds": sum(float(case.get("duration_seconds") or 0.0) for case in self.cases),
            "artifacts_generated": len({case["artifact_path"] for case in self.cases if case.get("artifact_path")}),
            "backtests_generated": len({case["backtest_run_id"] for case in completed if case.get("backtest_run_id")}),
            "research_runs_generated": len({case["research_run_id"] for case in completed if case.get("research_run_id")}),
            "latest_validation": latest_validation,
            **validation_details,
        }
        _write_json(
            OUTPUT_ROOT / "campaign_status.json",
            {"updated_at": summary["updated_at"], "phase": self.phase, "cases": self.cases},
        )
        _write_json(OUTPUT_ROOT / "completed_cases.json", completed)
        _write_json(OUTPUT_ROOT / "failed_cases.json", failed)
        _write_json(OUTPUT_ROOT / "campaign_summary.json", summary)
        if self.phase == "pilot":
            _write_json(OUTPUT_ROOT / "pilot_gate.json", self._pilot_gate(latest_validation))
        return summary

    def _pilot_gate(self, latest_validation: dict[str, Any] | None) -> dict[str, Any]:
        pilot = [case for case in self.cases if self._selected(case)]
        executable = [case for case in pilot if "_short_" not in case["target_name"]]
        unsupported = [case for case in pilot if "_short_" in case["target_name"]]
        manifest = _safe_json(OUTPUT_ROOT / "campaign_manifest.json") or {}
        baseline = manifest.get("baseline_validation") or {}
        checks = {
            "no_failed_or_running_cases": not any(case["status"] in {"failed", "running"} for case in pilot),
            "all_supported_cases_completed": bool(executable)
            and all(case["status"] == "completed" for case in executable),
            "all_artifacts_generated": bool(pilot) and all(case.get("artifact_path") for case in pilot),
            "all_backtests_completed": bool(executable)
            and all(case.get("backtest_run_id") for case in executable),
            "all_research_completed": bool(executable)
            and all(case.get("research_run_id") for case in executable),
            "unsupported_short_targets_explicitly_skipped": all(case["status"] == "skipped" for case in unsupported),
            "validation_coverage_increased": bool(latest_validation)
            and int(latest_validation.get("validated_cases") or 0)
            > int(baseline.get("validated_cases") or 0),
        }
        return {
            "evaluated_at": _now(),
            "passed": all(checks.values()),
            "checks": checks,
            "pilot_cases": len(pilot),
            "executable_cases": len(executable),
            "unsupported_short_cases": len(unsupported),
            "baseline_validation": baseline,
            "pilot_validation": latest_validation,
        }

    def _latest_validation_details(self) -> dict[str, Any]:
        candidates = []
        for run_dir in _run_dirs(VALIDATION_ROOT):
            if (run_dir / "validation_summary.json").is_file():
                candidates.append((run_dir.stat().st_mtime, run_dir))
        if not candidates:
            return {
                "best_asset": None,
                "best_target": None,
                "best_model": None,
                "best_oos_result": None,
            }
        _, run_dir = max(candidates)
        asset_ranking = _safe_json(run_dir / "asset_ranking.json") or []
        target_ranking = _safe_json(run_dir / "target_ranking.json") or []
        model_ranking = _safe_json(run_dir / "model_ranking.json") or []
        cases = _safe_json(run_dir / "case_results.json") or []
        best_oos = max(
            cases,
            key=lambda row: (
                float((row.get("out_of_sample") or {}).get("net_profit") or 0.0),
                float(row.get("score") or 0.0),
            ),
            default=None,
        )
        return {
            "best_asset": asset_ranking[0] if asset_ranking else None,
            "best_target": target_ranking[0] if target_ranking else None,
            "best_model": model_ranking[0] if model_ranking else None,
            "best_oos_result": best_oos,
        }


def _empty_case(case_id: str, symbol: str, target: str, model: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "symbol": symbol,
        "interval": INTERVAL,
        "target_name": target,
        "model_name": model,
        "artifact_path": None,
        "backtest_run_id": None,
        "research_run_id": None,
        "validation_run_id": None,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "duration_seconds": None,
        "error_message": None,
    }


def _manifest_artifacts() -> dict[tuple[str, str, str, str], str]:
    payload = _safe_json(ARTIFACTS_ROOT / "manifest.json") or {}
    return {
        (
            str(row.get("symbol")),
            str(row.get("interval")),
            str(row.get("target_name")),
            str(row.get("model_name")),
        ): str(row.get("artifact_dir"))
        for row in payload.get("models", [])
    }


def _research_by_backtest() -> dict[str, str]:
    result = {}
    for run_dir in _run_dirs(RESEARCH_ROOT):
        metadata = _safe_json(run_dir / "run_metadata.json")
        if metadata and metadata.get("source_backtest_run_id"):
            result[str(metadata["source_backtest_run_id"])] = str(metadata.get("research_run_id") or run_dir.name)
    return result


def _validation_by_backtest() -> dict[str, str]:
    result = {}
    for run_dir in _run_dirs(VALIDATION_ROOT):
        cases = _safe_json(run_dir / "case_results.json") or []
        for case in cases:
            if case.get("case_id"):
                result[str(case["case_id"])] = run_dir.name
    return result


def _run_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def _case_id(symbol: str, interval: str, target: str, model: str) -> str:
    raw = f"{symbol}|{interval}|{target}|{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _campaign_id(targets: tuple[str, ...]) -> str:
    raw = json.dumps({"assets": ASSETS, "interval": INTERVAL, "targets": targets, "models": MODELS, "seed": SEED})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(path: Path) -> Any:
    try:
        return _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the VinanceOS quantitative experiment campaign")
    parser.add_argument("--phase", choices=("pilot", "full"), required=True)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    summary = ExperimentCampaign(phase=args.phase, retry_failed=args.retry_failed).run()
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary["phase_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

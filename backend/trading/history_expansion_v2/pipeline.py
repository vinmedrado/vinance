from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.engine import Engine

from backend.trading.config import get_settings
from backend.trading.feature_store.pipeline import FeatureStorePipeline
from backend.trading.feature_store.repository import FeatureStoreRepository
from backend.trading.storage.database import create_sync_engine
from backend.trading.target_engine.pipeline import TargetEnginePipeline
from backend.trading.target_engine.repository import TargetRepository

from .config import HistoryExpansionConfig
from .downloader import HistoryDownloader
from .integrity import find_gap_ranges, last_closed_open_time, merge_ranges
from .models import ExpansionCaseResult, ExpansionResult, HistoryScope
from .reports import ExpansionReportWriter
from .repository import HistoryExpansionRepository
from .validator import HistoryValidator


FeatureRunner = Callable[[HistoryScope, int], dict[str, Any]]
TargetRunner = Callable[[HistoryScope, int], dict[str, Any]]


class _FullHistoryFeatureRepository(FeatureStoreRepository):
    def __init__(self, engine: Engine, batch_size: int) -> None:
        super().__init__(engine)
        self.batch_size = batch_size

    def get_last_feature_time(self, symbol, interval, exchange, feature_version):
        return None

    def persist_features(self, frame, feature_columns, feature_version, *, only_after=None):
        total = 0
        for start in range(0, len(frame), self.batch_size):
            total += super().persist_features(
                frame.iloc[start : start + self.batch_size],
                feature_columns,
                feature_version,
                only_after=only_after,
            )
        return total


class _FullHistoryTargetRepository(TargetRepository):
    def __init__(self, engine: Engine, batch_size: int) -> None:
        super().__init__(engine)
        self.batch_size = batch_size

    def get_last_target_time(self, symbol, interval, exchange, specs):
        return None

    def persist_targets(self, frame, specs, *, only_after=None):
        total = 0
        for start in range(0, len(frame), self.batch_size):
            total += super().persist_targets(
                frame.iloc[start : start + self.batch_size],
                specs,
                only_after=only_after,
            )
        return total


class HistoryExpansionPipeline:
    def __init__(
        self,
        repository: HistoryExpansionRepository,
        downloader: HistoryDownloader,
        config: HistoryExpansionConfig,
        *,
        feature_runner: FeatureRunner | None = None,
        target_runner: TargetRunner | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.downloader = downloader
        self.config = config
        self.validator = HistoryValidator(config)
        self.writer = ExpansionReportWriter(config.output_root)
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        engine = getattr(repository, "engine", None)
        self.feature_runner = feature_runner or self._feature_runner(engine)
        self.target_runner = target_runner or self._target_runner(engine)

    def run(self) -> ExpansionResult:
        started_perf = time.perf_counter()
        started_at = self.now_fn().astimezone(timezone.utc)
        self.repository.ensure_schema()
        scopes = self._ordered_scopes(self.repository.discover_scopes(self.config.exchange))
        if not scopes:
            raise RuntimeError(f"No existing candle scopes found for exchange={self.config.exchange}")
        run_id = _run_id(started_at, scopes, self.config)
        cases = [ExpansionCaseResult(scope=scope) for scope in scopes]
        self.writer.write(
            "expansion_manifest",
            {
                "run_id": run_id,
                "created_at": started_at,
                "paper_only": True,
                "source_provider": "backend.trading.market_data.binance_public.BinancePublicProvider",
                "history_months": self.config.history_months,
                "target_history_days": self.config.target_history_days,
                "persistence_batch_size": self.config.persistence_batch_size,
                "scopes": [scope for scope in scopes],
                "feature_store": "v2",
                "target_engine": "v2",
                "forbidden_stages": ["ml_engine", "backtesting", "research", "validation", "live_trading"],
            },
        )
        self._persist_status(run_id, cases)

        download_reports: list[dict[str, Any]] = []
        for case in cases:
            case_started = time.perf_counter()
            case.started_at = self.now_fn().astimezone(timezone.utc)
            case.status = "running"
            self._persist_status(run_id, cases)
            try:
                download_report = self._expand_case(case)
                download_reports.append(download_report)
                case.status = "downloaded"
            except Exception as exc:
                case.status = "failed"
                case.error_message = f"{type(exc).__name__}: {exc}"
            finally:
                case.finished_at = self.now_fn().astimezone(timezone.utc)
                case.duration_seconds = time.perf_counter() - case_started
                self._persist_status(run_id, cases)

        pipeline_reports: list[dict[str, Any]] = []
        for case in cases:
            if case.status != "downloaded" or case.integrity is None or not case.integrity.integrity_final:
                continue
            case_started = time.perf_counter()
            case.status = "processing"
            case.error_message = None
            self._persist_status(run_id, cases)
            try:
                feature_before = self.repository.feature_count(case.scope)
                target_before = self.repository.target_count(case.scope)
                feature_expected = max(case.final_candles - 1, 0)
                target_expected = max(case.final_candles - 1, 0) * 4
                if case.new_candles > 0 or feature_before < feature_expected:
                    case.feature_store = self.feature_runner(case.scope, case.final_candles)
                else:
                    case.feature_store = {
                        "skipped": True,
                        "reason": "already_current",
                        "rows_before": feature_before,
                    }
                if case.new_candles > 0 or target_before < target_expected:
                    case.target_engine = self.target_runner(case.scope, case.final_candles)
                else:
                    case.target_engine = {
                        "skipped": True,
                        "reason": "already_current",
                        "rows_before": target_before,
                    }
                case.feature_store["rows_after"] = self.repository.feature_count(case.scope)
                case.target_engine["rows_after"] = self.repository.target_count(case.scope)
                case.status = "completed"
                pipeline_reports.append(
                    {
                        "scope": case.scope,
                        "feature_store": case.feature_store,
                        "target_engine": case.target_engine,
                    }
                )
            except Exception as exc:
                case.status = "failed"
                case.error_message = f"{type(exc).__name__}: {exc}"
            finally:
                case.finished_at = self.now_fn().astimezone(timezone.utc)
                case.duration_seconds = float(case.duration_seconds or 0.0) + (time.perf_counter() - case_started)
                self._persist_status(run_id, cases)

        finished_at = self.now_fn().astimezone(timezone.utc)
        result = ExpansionResult(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=time.perf_counter() - started_perf,
            cases=cases,
            output_root=str(self.config.output_root),
        )
        self.writer.write("download_report", {"run_id": run_id, "cases": download_reports})
        self.writer.write(
            "integrity_report",
            {"run_id": run_id, "cases": [case.integrity for case in cases if case.integrity is not None]},
        )
        self.writer.write("pipeline_report", {"run_id": run_id, "cases": pipeline_reports})
        self.writer.write("expansion_summary", self._summary(result))
        self._persist_status(run_id, cases)
        return result

    def _expand_case(self, case: ExpansionCaseResult) -> dict[str, Any]:
        scope = case.scope
        interval_seconds = self.config.interval_seconds(scope.interval)
        step = timedelta(seconds=interval_seconds)
        desired_end = last_closed_open_time(self.now_fn(), interval_seconds)
        desired_start = desired_end - timedelta(days=self.config.target_history_days)
        before = self.repository.snapshot(scope)
        case.old_candles = before.candle_count
        existing = self.repository.load_history(scope, start=desired_start, end=desired_end)
        ranges: list[tuple[datetime, datetime]] = []
        if before.first_candle is None or before.last_candle is None:
            ranges.append((desired_start, desired_end))
        else:
            first = before.first_candle.astimezone(timezone.utc)
            last = before.last_candle.astimezone(timezone.utc)
            if first > desired_start:
                ranges.append((desired_start, min(first - step, desired_end)))
            for gap in find_gap_ranges(existing.get("open_time", []), interval_seconds):
                ranges.append((gap.start, gap.end))
            if last < desired_end:
                ranges.append((max(last + step, desired_start), desired_end))
        planned = merge_ranges(ranges, interval_seconds)
        requests = 0
        downloaded = 0
        persisted = 0
        duplicates_removed = 0
        for range_start, range_end in planned:
            for batch in self.downloader.iter_batches(scope, range_start, range_end):
                requests += 1
                self.validator.require_download_safe(batch.frame, scope)
                downloaded += int(len(batch.frame))
                duplicates_removed += batch.duplicates_removed
                persisted += self.repository.upsert_candles(batch.frame)
        after = self.repository.snapshot(scope)
        case.new_candles = max(after.candle_count - before.candle_count, 0)
        case.final_candles = after.candle_count
        case.duplicates_removed = duplicates_removed
        final_history = self.repository.load_history(scope)
        case.integrity = self.validator.validate(
            final_history,
            scope,
            duplicates_removed=duplicates_removed,
        )
        if not case.integrity.integrity_final:
            raise ValueError(
                f"Final history integrity failed for {scope.key}: score={case.integrity.integrity_score:.6f}"
            )
        return {
            "scope": scope,
            "desired_start": desired_start,
            "desired_end": desired_end,
            "ranges": [{"start": start, "end": end} for start, end in planned],
            "requests": requests,
            "downloaded_rows": downloaded,
            "persisted_rows": persisted,
            "duplicates_removed": duplicates_removed,
            "old_candles": before.candle_count,
            "new_candles": case.new_candles,
            "final_candles": after.candle_count,
        }

    def _ordered_scopes(self, scopes: list[HistoryScope]) -> list[HistoryScope]:
        supported = [scope for scope in scopes if scope.interval in self.config.preferred_intervals]
        other_supported = [
            scope
            for scope in scopes
            if scope.interval not in self.config.preferred_intervals
            and _is_supported_interval(self.config, scope.interval)
        ]
        selected = supported + other_supported
        asset_rank = {asset: index for index, asset in enumerate(self.config.preferred_assets)}
        interval_rank = {interval: index for index, interval in enumerate(self.config.preferred_intervals)}
        return sorted(
            selected,
            key=lambda scope: (
                asset_rank.get(scope.symbol, len(asset_rank)),
                scope.symbol,
                interval_rank.get(scope.interval, len(interval_rank)),
                scope.interval,
            ),
        )

    def _persist_status(self, run_id: str, cases: list[ExpansionCaseResult]) -> None:
        self.writer.write(
            "expansion_status",
            {
                "run_id": run_id,
                "updated_at": self.now_fn().astimezone(timezone.utc),
                "cases": cases,
            },
        )

    def _summary(self, result: ExpansionResult) -> dict[str, Any]:
        completed = [case for case in result.cases if case.status == "completed"]
        failed = [case for case in result.cases if case.status == "failed"]
        return {
            "run_id": result.run_id,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "duration_seconds": result.duration_seconds,
            "assets_processed": sorted({case.scope.symbol for case in completed}),
            "intervals_processed": sorted({case.scope.interval for case in completed}),
            "total_scopes": len(result.cases),
            "completed_scopes": len(completed),
            "failed_scopes": len(failed),
            "old_candles": sum(case.old_candles for case in result.cases),
            "new_candles": sum(case.new_candles for case in result.cases),
            "final_candles": sum(case.final_candles for case in result.cases),
            "duplicates_removed": sum(case.duplicates_removed for case in result.cases),
            "gaps_found": sum(case.integrity.gap_count for case in result.cases if case.integrity),
            "missing_candles": sum(case.integrity.missing_candles for case in result.cases if case.integrity),
            "integrity_final": bool(completed) and not failed and all(
                case.integrity and case.integrity.integrity_final for case in completed
            ),
            "cases": result.cases,
        }

    def _feature_runner(self, engine: Engine | None) -> FeatureRunner:
        if engine is None:
            raise ValueError("feature_runner is required when repository has no engine")
        repository = _FullHistoryFeatureRepository(engine, self.config.persistence_batch_size)
        pipeline = FeatureStorePipeline(engine, repository=repository)

        def run(scope: HistoryScope, candle_count: int) -> dict[str, Any]:
            result = pipeline.run_symbol(
                scope.symbol,
                scope.interval,
                scope.exchange,
                limit=max(candle_count, 1),
            )
            return asdict(result)

        return run

    def _target_runner(self, engine: Engine | None) -> TargetRunner:
        if engine is None:
            raise ValueError("target_runner is required when repository has no engine")
        repository = _FullHistoryTargetRepository(engine, self.config.persistence_batch_size)
        pipeline = TargetEnginePipeline(engine, repository=repository)

        def run(scope: HistoryScope, candle_count: int) -> dict[str, Any]:
            result = pipeline.run_symbol(
                scope.symbol,
                scope.interval,
                scope.exchange,
                limit=max(candle_count, 1),
            )
            return asdict(result)

        return run


def run_history_expansion(config: HistoryExpansionConfig | None = None) -> ExpansionResult:
    resolved = config or HistoryExpansionConfig()
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        raise RuntimeError("History Expansion V2 requires TRADING_MODE=PAPER_ONLY")
    engine = create_sync_engine(settings.database_url)
    try:
        repository = HistoryExpansionRepository(engine)
        downloader = HistoryDownloader(resolved)
        return HistoryExpansionPipeline(repository, downloader, resolved).run()
    finally:
        engine.dispose()


def _is_supported_interval(config: HistoryExpansionConfig, interval: str) -> bool:
    try:
        config.interval_seconds(interval)
    except ValueError:
        return False
    return True


def _run_id(started_at: datetime, scopes: list[HistoryScope], config: HistoryExpansionConfig) -> str:
    raw = json.dumps(
        {
            "started_at": started_at.isoformat(),
            "scopes": [scope.key for scope in scopes],
            "history_months": config.history_months,
            "version": config.version,
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand VinanceOS Trading V2 candle history")
    parser.add_argument("--months", type=int, default=24, choices=range(12, 25))
    args = parser.parse_args()
    result = run_history_expansion(HistoryExpansionConfig(history_months=args.months))
    failed = sum(case.status == "failed" for case in result.cases)
    print(f"history_expansion_run_id={result.run_id}")
    print(f"scopes={len(result.cases)} failed={failed} duration_seconds={result.duration_seconds:.2f}")
    print(f"reports={Path(result.output_root)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

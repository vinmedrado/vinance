from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.trading.history_expansion_v2.config import HistoryExpansionConfig
from backend.trading.history_expansion_v2.downloader import HistoryDownloader
from backend.trading.history_expansion_v2.models import HistoryScope
from backend.trading.history_expansion_v2.pipeline import HistoryExpansionPipeline

from .helpers import FakeProvider, InMemoryHistoryRepository, candle_frame


def _pipeline(tmp_path):
    now = datetime(2026, 1, 2, 12, 2, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, 11, 55, tzinfo=timezone.utc)
    start = end - timedelta(days=1)
    universe = candle_frame(start, 289)
    scope = HistoryScope("binance", "BTCUSDT", "5m")
    repository = InMemoryHistoryRepository(universe.iloc[100:].copy(), scope)
    provider = FakeProvider(universe)
    config = HistoryExpansionConfig(
        history_days_override=1,
        page_limit=37,
        request_pause_seconds=0,
        output_root=tmp_path,
    )
    feature_calls = []
    target_calls = []

    def features(item, candle_count):
        feature_calls.append((item, candle_count))
        repository.features = candle_count - 1
        return {"rows_persisted": candle_count - 1}

    def targets(item, candle_count):
        target_calls.append((item, candle_count))
        repository.targets = (candle_count - 1) * 4
        return {"targets_persisted": (candle_count - 1) * 4}

    pipeline = HistoryExpansionPipeline(
        repository,
        HistoryDownloader(config, provider=provider, sleep_fn=lambda _: None),
        config,
        feature_runner=features,
        target_runner=targets,
        now_fn=lambda: now,
    )
    return pipeline, repository, provider, feature_calls, target_calls


def test_incremental_update_backfills_only_missing_history(tmp_path) -> None:
    pipeline, repository, provider, feature_calls, target_calls = _pipeline(tmp_path)
    result = pipeline.run()
    case = result.cases[0]
    assert case.status == "completed"
    assert case.old_candles == 189
    assert case.new_candles == 100
    assert case.final_candles == 289
    assert len(provider.calls) == 3
    assert len(feature_calls) == len(target_calls) == 1
    assert case.integrity and case.integrity.integrity_final
    assert len(repository.frame) == 289


def test_idempotent_second_run_downloads_nothing(tmp_path) -> None:
    pipeline, repository, provider, feature_calls, target_calls = _pipeline(tmp_path)
    first = pipeline.run()
    calls_after_first = len(provider.calls)
    second = pipeline.run()
    assert first.cases[0].new_candles == 100
    assert second.cases[0].new_candles == 0
    assert len(provider.calls) == calls_after_first
    assert len(repository.frame) == 289
    assert len(feature_calls) == len(target_calls) == 1

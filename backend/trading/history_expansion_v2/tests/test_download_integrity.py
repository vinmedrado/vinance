from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from backend.trading.history_expansion_v2.config import HistoryExpansionConfig
from backend.trading.history_expansion_v2.downloader import HistoryDownloader
from backend.trading.history_expansion_v2.integrity import coverage_months, deduplicate_candles, find_gap_ranges
from backend.trading.history_expansion_v2.models import HistoryScope
from backend.trading.history_expansion_v2.validator import HistoryValidator

from .helpers import FakeProvider, candle_frame


SCOPE = HistoryScope("binance", "BTCUSDT", "5m")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_download_paginates_existing_binance_provider_contract() -> None:
    universe = candle_frame(START, 7)
    provider = FakeProvider(universe)
    config = HistoryExpansionConfig(history_days_override=1, page_limit=3, request_pause_seconds=0)
    batches = list(
        HistoryDownloader(config, provider=provider, sleep_fn=lambda _: None).iter_batches(
            SCOPE,
            START,
            START + timedelta(minutes=30),
        )
    )
    assert [len(batch.frame) for batch in batches] == [3, 3, 1]
    assert len(provider.calls) == 3
    assert pd.concat([batch.frame for batch in batches])["open_time"].is_monotonic_increasing


def test_deduplication_keeps_one_natural_key() -> None:
    frame = candle_frame(START, 4)
    duplicate = frame.iloc[[2]].copy()
    duplicate["close"] = 999.0
    deduplicated, removed = deduplicate_candles(pd.concat([frame, duplicate], ignore_index=True))
    assert removed == 1
    assert len(deduplicated) == 4
    assert deduplicated.loc[deduplicated["open_time"] == frame.iloc[2]["open_time"], "close"].item() == 999.0


def test_gap_detection_counts_missing_candles() -> None:
    frame = candle_frame(START, 6).drop(index=[2, 3]).reset_index(drop=True)
    gaps = find_gap_ranges(frame["open_time"], 300)
    assert len(gaps) == 1
    assert gaps[0].missing_candles == 2
    assert gaps[0].start == START + timedelta(minutes=10)


def test_timezone_validation_rejects_naive_timestamps() -> None:
    frame = candle_frame(START, 3)
    frame["open_time"] = frame["open_time"].dt.tz_localize(None)
    result = HistoryValidator(HistoryExpansionConfig(history_days_override=1)).validate(frame, SCOPE)
    assert result.timezone_invalid == 3
    assert result.integrity_final is False


def test_integrity_detects_invalid_ohlc_and_volume() -> None:
    frame = candle_frame(START, 3)
    frame.loc[1, "high"] = 1.0
    frame.loc[2, "volume"] = -1.0
    result = HistoryValidator(HistoryExpansionConfig(history_days_override=1)).validate(frame, SCOPE)
    assert result.invalid_ohlc == 1
    assert result.invalid_volume == 1
    assert result.integrity_final is False


def test_coverage_temporal_is_reported_in_months() -> None:
    assert 11.99 < coverage_months(START, START + timedelta(days=365.25)) < 12.01

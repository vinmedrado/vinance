from __future__ import annotations

import math

import pandas as pd

from .config import HistoryExpansionConfig
from .integrity import coverage_months, find_gap_ranges
from .models import HistoryScope, IntegrityResult


REQUIRED_COLUMNS = (
    "exchange",
    "symbol",
    "interval",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class HistoryValidator:
    def __init__(self, config: HistoryExpansionConfig) -> None:
        self.config = config

    def validate(
        self,
        frame: pd.DataFrame,
        scope: HistoryScope,
        *,
        duplicates_removed: int = 0,
    ) -> IntegrityResult:
        missing_columns = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
        if missing_columns:
            raise ValueError(f"Missing candle columns: {missing_columns}")
        step_seconds = self.config.interval_seconds(scope.interval)
        if frame.empty:
            return IntegrityResult(
                scope=scope,
                candle_count=0,
                first_candle=None,
                last_candle=None,
                coverage_seconds=0.0,
                coverage_months=0.0,
                expected_candles=0,
                missing_candles=0,
                gap_count=0,
                gap_percentage=0.0,
                duplicate_count=0,
                duplicates_removed=duplicates_removed,
                duplicate_percentage=0.0,
                invalid_timestamps=0,
                timezone_invalid=0,
                chronological_violations=0,
                timestamp_alignment_violations=0,
                invalid_ohlc=0,
                invalid_volume=0,
                integrity_score=0.0,
                integrity_final=False,
            )

        raw_times = frame["open_time"]
        parsed = pd.to_datetime(raw_times, errors="coerce")
        invalid_timestamps = int(parsed.isna().sum())
        timezone_invalid = _timezone_invalid_count(parsed)
        utc_times = pd.to_datetime(raw_times, utc=True, errors="coerce")
        valid_times = utc_times.dropna()
        chronological_violations = int((valid_times.diff().dropna().dt.total_seconds() <= 0).sum())
        duplicate_count = int(frame.duplicated(["exchange", "symbol", "interval", "open_time"]).sum())
        alignment_violations = int(
            sum(int(item.timestamp()) % step_seconds != 0 for item in valid_times.array)
        )

        numeric = frame[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
        price_nan = numeric[["open", "high", "low", "close"]].isna().any(axis=1)
        non_positive = (numeric[["open", "high", "low", "close"]] <= 0).any(axis=1)
        high_invalid = numeric["high"] < numeric[["open", "low", "close"]].max(axis=1)
        low_invalid = numeric["low"] > numeric[["open", "high", "close"]].min(axis=1)
        invalid_ohlc = int((price_nan | non_positive | high_invalid | low_invalid).sum())
        invalid_volume = int((numeric["volume"].isna() | (numeric["volume"] < 0)).sum())

        gaps = find_gap_ranges(valid_times, step_seconds)
        missing_candles = sum(gap.missing_candles for gap in gaps)
        first = valid_times.min().to_pydatetime() if not valid_times.empty else None
        last = valid_times.max().to_pydatetime() if not valid_times.empty else None
        coverage_seconds = (last - first).total_seconds() if first and last else 0.0
        expected = int(round(coverage_seconds / step_seconds)) + 1 if first and last else len(valid_times)
        gap_percentage = 100.0 * missing_candles / expected if expected else 0.0
        duplicate_percentage = 100.0 * duplicate_count / max(len(frame), 1)
        critical = (
            invalid_timestamps
            + timezone_invalid
            + chronological_violations
            + alignment_violations
            + duplicate_count
            + invalid_ohlc
            + invalid_volume
        )
        critical_percentage = 100.0 * critical / max(len(frame), 1)
        score = max(0.0, 100.0 - gap_percentage - duplicate_percentage - critical_percentage)
        final = critical == 0 and gap_percentage <= self.config.max_gap_percentage
        return IntegrityResult(
            scope=scope,
            candle_count=int(len(frame)),
            first_candle=first,
            last_candle=last,
            coverage_seconds=coverage_seconds,
            coverage_months=coverage_months(first, last),
            expected_candles=expected,
            missing_candles=missing_candles,
            gap_count=len(gaps),
            gap_percentage=gap_percentage,
            duplicate_count=duplicate_count,
            duplicates_removed=duplicates_removed,
            duplicate_percentage=duplicate_percentage,
            invalid_timestamps=invalid_timestamps,
            timezone_invalid=timezone_invalid,
            chronological_violations=chronological_violations,
            timestamp_alignment_violations=alignment_violations,
            invalid_ohlc=invalid_ohlc,
            invalid_volume=invalid_volume,
            integrity_score=score if math.isfinite(score) else 0.0,
            integrity_final=final,
            gaps=gaps,
        )

    def require_download_safe(self, frame: pd.DataFrame, scope: HistoryScope) -> IntegrityResult:
        result = self.validate(frame, scope)
        unsafe = (
            result.invalid_timestamps
            + result.timezone_invalid
            + result.chronological_violations
            + result.timestamp_alignment_violations
            + result.invalid_ohlc
            + result.invalid_volume
        )
        if unsafe:
            raise ValueError(f"Downloaded candles failed validation for {scope.key}: {result}")
        return result


def _timezone_invalid_count(series: pd.Series) -> int:
    try:
        timezone = series.dt.tz
    except (AttributeError, TypeError):
        return int(len(series))
    return int(len(series)) if timezone is None else 0

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from .models import GapRange


NATURAL_KEY = ("exchange", "symbol", "interval", "open_time")


def deduplicate_candles(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        return frame.copy(), 0
    result = frame.copy()
    duplicated = result.duplicated(list(NATURAL_KEY), keep="last")
    removed = int(duplicated.sum())
    result = result.loc[~duplicated].sort_values("open_time").reset_index(drop=True)
    return result, removed


def find_gap_ranges(open_times: pd.Series, interval_seconds: int) -> tuple[GapRange, ...]:
    if len(open_times) < 2:
        return ()
    ordered = pd.to_datetime(open_times, utc=True, errors="coerce").dropna().drop_duplicates().sort_values()
    step = timedelta(seconds=interval_seconds)
    gaps: list[GapRange] = []
    previous = None
    for current in ordered:
        current_dt = current.to_pydatetime()
        if previous is not None:
            delta_seconds = (current_dt - previous).total_seconds()
            missing = max(int(round(delta_seconds / interval_seconds)) - 1, 0)
            if missing:
                gaps.append(
                    GapRange(
                        start=previous + step,
                        end=current_dt - step,
                        missing_candles=missing,
                    )
                )
        previous = current_dt
    return tuple(gaps)


def coverage_months(first: datetime | None, last: datetime | None) -> float:
    if first is None or last is None or last < first:
        return 0.0
    return (last - first).total_seconds() / (365.25 / 12.0 * 86_400.0)


def last_closed_open_time(now: datetime, interval_seconds: int) -> datetime:
    resolved = ensure_utc(now)
    epoch = int(resolved.timestamp())
    current_open = epoch - epoch % interval_seconds
    return datetime.fromtimestamp(current_open - interval_seconds, tz=timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def merge_ranges(ranges: list[tuple[datetime, datetime]], interval_seconds: int) -> list[tuple[datetime, datetime]]:
    usable = sorted((ensure_utc(start), ensure_utc(end)) for start, end in ranges if start <= end)
    if not usable:
        return []
    step = timedelta(seconds=interval_seconds)
    merged = [usable[0]]
    for start, end in usable[1:]:
        prior_start, prior_end = merged[-1]
        if start <= prior_end + step:
            merged[-1] = (prior_start, max(prior_end, end))
        else:
            merged.append((start, end))
    return merged

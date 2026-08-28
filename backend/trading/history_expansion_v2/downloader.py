from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd

from backend.trading.market_data.binance_public import BinancePublicProvider

from .config import HistoryExpansionConfig
from .integrity import deduplicate_candles, ensure_utc
from .models import DownloadBatch, HistoryScope


class HistoryDownloader:
    """Paginates the project's existing Binance public provider."""

    def __init__(
        self,
        config: HistoryExpansionConfig,
        provider: BinancePublicProvider | None = None,
        *,
        sleep_fn=time.sleep,
    ) -> None:
        self.config = config
        self.provider = provider or BinancePublicProvider()
        self.sleep_fn = sleep_fn

    def iter_batches(
        self,
        scope: HistoryScope,
        start: datetime,
        end: datetime,
    ) -> Iterator[DownloadBatch]:
        cursor = ensure_utc(start)
        resolved_end = ensure_utc(end)
        step = timedelta(seconds=self.config.interval_seconds(scope.interval))
        seen: set[pd.Timestamp] = set()
        while cursor <= resolved_end:
            raw = self.provider.fetch_candles(
                symbol=scope.symbol,
                interval=scope.interval,
                start=cursor,
                end=resolved_end,
                limit=self.config.page_limit,
            )
            if raw.empty:
                break
            frame = raw.copy()
            frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True, errors="coerce")
            frame = frame[(frame["open_time"] >= cursor) & (frame["open_time"] <= resolved_end)]
            frame, duplicates_removed = deduplicate_candles(frame)
            if seen and not frame.empty:
                repeated = frame["open_time"].isin(seen)
                duplicates_removed += int(repeated.sum())
                frame = frame.loc[~repeated].reset_index(drop=True)
            if frame.empty:
                break
            seen.update(frame["open_time"].tolist())
            yield DownloadBatch(frame=frame, duplicates_removed=duplicates_removed)
            last_open = frame["open_time"].iloc[-1].to_pydatetime()
            next_cursor = last_open + step
            if next_cursor <= cursor:
                raise RuntimeError(f"Download cursor did not advance for {scope.key}")
            cursor = next_cursor
            if len(raw) < self.config.page_limit:
                break
            if self.config.request_pause_seconds:
                self.sleep_fn(self.config.request_pause_seconds)

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from backend.trading.history_expansion_v2.integrity import deduplicate_candles
from backend.trading.history_expansion_v2.models import HistoryScope, HistorySnapshot


def candle_frame(
    start: datetime,
    rows: int,
    *,
    interval_seconds: int = 300,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
) -> pd.DataFrame:
    times = pd.date_range(start, periods=rows, freq=f"{interval_seconds}s", tz="UTC")
    base = pd.Series(range(rows), dtype=float) * 0.01 + 100.0
    return pd.DataFrame(
        {
            "exchange": "binance",
            "symbol": symbol,
            "interval": interval,
            "open_time": times,
            "close_time": times + pd.Timedelta(seconds=interval_seconds - 1),
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + 0.2,
            "volume": 10.0,
            "quote_volume": 1_000.0,
            "trades": 100,
        }
    )


class FakeProvider:
    def __init__(self, universe: pd.DataFrame) -> None:
        self.universe = universe.copy()
        self.calls: list[tuple[datetime, datetime, int]] = []

    def fetch_candles(self, symbol, interval, start=None, end=None, limit=1000):
        self.calls.append((start, end, limit))
        selected = self.universe[
            (self.universe["symbol"] == symbol)
            & (self.universe["interval"] == interval)
            & (self.universe["open_time"] >= start)
            & (self.universe["open_time"] <= end)
        ]
        return selected.head(limit).reset_index(drop=True)


class InMemoryHistoryRepository:
    def __init__(self, frame: pd.DataFrame, scope: HistoryScope) -> None:
        self.frame = frame.copy()
        self.scope = scope
        self.features = max(len(frame) - 1, 0)
        self.targets = max(len(frame) - 1, 0) * 4

    def ensure_schema(self):
        return None

    def discover_scopes(self, exchange):
        return [self.scope]

    def snapshot(self, scope):
        if self.frame.empty:
            return HistorySnapshot(scope, 0, None, None)
        return HistorySnapshot(
            scope,
            len(self.frame),
            self.frame["open_time"].min().to_pydatetime(),
            self.frame["open_time"].max().to_pydatetime(),
        )

    def load_history(self, scope, *, start=None, end=None):
        frame = self.frame.copy()
        if start is not None:
            frame = frame[frame["open_time"] >= start]
        if end is not None:
            frame = frame[frame["open_time"] <= end]
        return frame.sort_values("open_time").reset_index(drop=True)

    def upsert_candles(self, frame):
        combined = pd.concat([self.frame, frame], ignore_index=True)
        self.frame, _ = deduplicate_candles(combined)
        return len(frame)

    def feature_count(self, scope):
        return self.features

    def target_count(self, scope):
        return self.targets

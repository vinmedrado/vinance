from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .models import MarketCandle


class PaperTradingRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load_entry_candle(self, *, candle_id: int, symbol: str, interval: str) -> MarketCandle:
        query = text(
            """
            SELECT id, symbol, interval, open_time, open, high, low, close
            FROM crypto_candles
            WHERE id = :candle_id
              AND symbol = :symbol
              AND interval = :interval
            LIMIT 1
            """
        )
        with self.engine.connect() as connection:
            row = connection.execute(query, {"candle_id": candle_id, "symbol": symbol, "interval": interval}).mappings().first()
        if row is None:
            raise LookupError(f"Entry candle not found for id={candle_id} symbol={symbol} interval={interval}")
        return _row_to_candle(row)

    def load_future_candles(self, *, symbol: str, interval: str, after_open_time, limit: int) -> list[MarketCandle]:
        query = text(
            """
            SELECT id, symbol, interval, open_time, open, high, low, close
            FROM crypto_candles
            WHERE symbol = :symbol
              AND interval = :interval
              AND open_time > :after_open_time
            ORDER BY open_time ASC
            LIMIT :limit
            """
        )
        frame = pd.read_sql(
            query,
            self.engine,
            params={"symbol": symbol, "interval": interval, "after_open_time": after_open_time, "limit": limit},
        )
        return [_row_to_candle(row) for row in frame.to_dict("records")]


def _row_to_candle(row) -> MarketCandle:
    return MarketCandle(
        candle_id=int(row["id"]),
        symbol=str(row["symbol"]),
        interval=str(row["interval"]),
        open_time=row["open_time"],
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
    )

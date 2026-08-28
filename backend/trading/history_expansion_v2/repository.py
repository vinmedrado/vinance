from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.trading.storage.repositories import CandleRepository

from .models import HistoryScope, HistorySnapshot


class HistoryExpansionRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.candles = CandleRepository(engine)

    def ensure_schema(self) -> None:
        query = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('crypto_candles', 'crypto_features', 'crypto_targets')
            """
        )
        with self.engine.connect() as connection:
            found = {row[0] for row in connection.execute(query)}
        missing = {"crypto_candles", "crypto_features", "crypto_targets"}.difference(found)
        if missing:
            raise RuntimeError(f"Trading schema is missing required tables: {sorted(missing)}")

    def discover_scopes(self, exchange: str) -> list[HistoryScope]:
        query = text(
            """
            SELECT DISTINCT exchange, symbol, interval
            FROM crypto_candles
            WHERE LOWER(exchange) = LOWER(:exchange)
            ORDER BY symbol, interval
            """
        )
        with self.engine.connect() as connection:
            return [
                HistoryScope(exchange=str(row[0]), symbol=str(row[1]), interval=str(row[2]))
                for row in connection.execute(query, {"exchange": exchange})
            ]

    def snapshot(self, scope: HistoryScope) -> HistorySnapshot:
        query = text(
            """
            SELECT COUNT(*), MIN(open_time), MAX(open_time)
            FROM crypto_candles
            WHERE LOWER(exchange) = LOWER(:exchange)
              AND symbol = :symbol
              AND interval = :interval
            """
        )
        with self.engine.connect() as connection:
            row = connection.execute(
                query,
                {"exchange": scope.exchange, "symbol": scope.symbol, "interval": scope.interval},
            ).one()
        return HistorySnapshot(
            scope=scope,
            candle_count=int(row[0] or 0),
            first_candle=row[1],
            last_candle=row[2],
        )

    def load_history(
        self,
        scope: HistoryScope,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        query = """
            SELECT exchange, symbol, interval, open_time, close_time,
                   open, high, low, close, volume, quote_volume, trades
            FROM crypto_candles
            WHERE LOWER(exchange) = LOWER(:exchange)
              AND symbol = :symbol
              AND interval = :interval
        """
        params: dict[str, object] = {
            "exchange": scope.exchange,
            "symbol": scope.symbol,
            "interval": scope.interval,
        }
        if start is not None:
            query += " AND open_time >= :start"
            params["start"] = start
        if end is not None:
            query += " AND open_time <= :end"
            params["end"] = end
        query += " ORDER BY open_time ASC"
        return pd.read_sql(text(query), self.engine, params=params)

    def upsert_candles(self, frame: pd.DataFrame) -> int:
        return self.candles.upsert_dataframe(frame)

    def feature_count(self, scope: HistoryScope, feature_version: str = "v2") -> int:
        query = text(
            """
            SELECT COUNT(*)
            FROM crypto_features f
            JOIN crypto_candles c ON c.id = f.candle_id
            WHERE LOWER(c.exchange) = LOWER(:exchange)
              AND c.symbol = :symbol
              AND c.interval = :interval
              AND f.feature_version = :version
            """
        )
        with self.engine.connect() as connection:
            return int(
                connection.execute(
                    query,
                    {
                        "exchange": scope.exchange,
                        "symbol": scope.symbol,
                        "interval": scope.interval,
                        "version": feature_version,
                    },
                ).scalar_one()
                or 0
            )

    def target_count(self, scope: HistoryScope, target_prefix: str = "v2_%") -> int:
        query = text(
            """
            SELECT COUNT(*)
            FROM crypto_targets t
            JOIN crypto_candles c ON c.id = t.candle_id
            WHERE LOWER(c.exchange) = LOWER(:exchange)
              AND c.symbol = :symbol
              AND c.interval = :interval
              AND t.target_name LIKE :prefix
            """
        )
        with self.engine.connect() as connection:
            return int(
                connection.execute(
                    query,
                    {
                        "exchange": scope.exchange,
                        "symbol": scope.symbol,
                        "interval": scope.interval,
                        "prefix": target_prefix,
                    },
                ).scalar_one()
                or 0
            )

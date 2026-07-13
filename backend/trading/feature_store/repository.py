from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import DEFAULT_CONFIG, FeatureStoreConfig


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) or np.isinf(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


class FeatureStoreRepository:
    def __init__(
        self,
        engine: Engine,
        config: FeatureStoreConfig = DEFAULT_CONFIG,
    ) -> None:
        self.engine = engine
        self.config = config

    def ensure_schema(self) -> None:
        query = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('crypto_candles', 'crypto_features')
            """
        )
        with self.engine.connect() as connection:
            tables = {row[0] for row in connection.execute(query)}
        missing = {"crypto_candles", "crypto_features"}.difference(tables)
        if missing:
            raise RuntimeError(
                "Trading schema is missing required tables: "
                f"{sorted(missing)}. Apply backend/trading/storage/schema.sql before running Feature Store V2."
            )

    def get_last_feature_time(self, symbol: str, interval: str, exchange: str, feature_version: str) -> datetime | None:
        query = text(
            """
            SELECT MAX(c.open_time)
            FROM crypto_features f
            JOIN crypto_candles c ON c.id = f.candle_id
            WHERE c.symbol = :symbol
              AND c.interval = :interval
              AND c.exchange = :exchange
              AND f.feature_version = :feature_version
            """
        )
        with self.engine.connect() as connection:
            return connection.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "exchange": exchange,
                    "feature_version": feature_version,
                },
            ).scalar_one_or_none()

    def count_candles(self, symbol: str, interval: str, exchange: str) -> int:
        query = text(
            """
            SELECT COUNT(*)
            FROM crypto_candles
            WHERE symbol = :symbol
              AND interval = :interval
              AND exchange = :exchange
            """
        )
        with self.engine.connect() as connection:
            return int(
                connection.execute(
                    query,
                    {"symbol": symbol, "interval": interval, "exchange": exchange},
                ).scalar_one()
                or 0
            )

    def load_full_history_for_build(
        self,
        symbol: str,
        interval: str,
        exchange: str,
        limit: int | None = None,
    ) -> tuple[pd.DataFrame, bool]:
        effective_limit = limit or self.config.default_limit
        total = self.count_candles(symbol=symbol, interval=interval, exchange=exchange)
        truncated = total > effective_limit
        query = text(
            """
            SELECT *
            FROM crypto_candles
            WHERE symbol = :symbol
              AND interval = :interval
              AND exchange = :exchange
            ORDER BY open_time DESC
            LIMIT :limit
            """
        )
        data = pd.read_sql(
            query,
            self.engine,
            params={"symbol": symbol, "interval": interval, "exchange": exchange, "limit": effective_limit},
        )
        if data.empty:
            return data, truncated
        return data.sort_values("open_time").reset_index(drop=True), truncated

    def persist_features(
        self,
        frame: pd.DataFrame,
        feature_columns: tuple[str, ...],
        feature_version: str,
        *,
        only_after: datetime | None = None,
    ) -> int:
        if frame.empty:
            return 0

        usable = frame.copy()
        if only_after is not None:
            usable = usable[usable["open_time"] > only_after]
        usable = usable.dropna(subset=["id"])
        if usable.empty:
            return 0

        rows: list[dict[str, Any]] = []
        for row in usable.itertuples(index=False):
            features = {column: json_safe(getattr(row, column, None)) for column in feature_columns}
            non_null_count = sum(value is not None for value in features.values())
            if non_null_count < self.config.min_non_null_features:
                continue
            rows.append(
                {
                    "candle_id": int(row.id),
                    "feature_version": feature_version,
                    "features": json.dumps(features, ensure_ascii=False),
                }
            )

        if not rows:
            return 0

        statement = text(
            """
            INSERT INTO crypto_features (candle_id, feature_version, features)
            VALUES (:candle_id, :feature_version, CAST(:features AS JSONB))
            ON CONFLICT (candle_id, feature_version)
            DO UPDATE SET features = EXCLUDED.features
            """
        )
        with self.engine.begin() as connection:
            connection.execute(statement, rows)
        return len(rows)

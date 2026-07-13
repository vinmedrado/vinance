from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import DEFAULT_CONFIG, TargetEngineConfig, TargetSpec


class TargetRepository:
    def __init__(self, engine: Engine, config: TargetEngineConfig = DEFAULT_CONFIG) -> None:
        self.engine = engine
        self.config = config

    def ensure_schema(self) -> None:
        query = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('crypto_candles', 'crypto_targets')
            """
        )
        with self.engine.connect() as connection:
            tables = {row[0] for row in connection.execute(query)}
        missing = {"crypto_candles", "crypto_targets"}.difference(tables)
        if missing:
            raise RuntimeError(
                "Trading schema is missing required tables: "
                f"{sorted(missing)}. Apply backend/trading/storage/schema.sql before running Target Engine V2."
            )

    def get_last_target_time(self, symbol: str, interval: str, exchange: str, specs: tuple[TargetSpec, ...]) -> datetime | None:
        target_names = tuple(spec.name for spec in specs)
        query = text(
            """
            SELECT MAX(c.open_time)
            FROM crypto_targets t
            JOIN crypto_candles c ON c.id = t.candle_id
            WHERE c.symbol = :symbol
              AND c.interval = :interval
              AND c.exchange = :exchange
              AND t.target_name = ANY(:target_names)
            """
        )
        with self.engine.connect() as connection:
            return connection.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval,
                    "exchange": exchange,
                    "target_names": list(target_names),
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
            return int(connection.execute(query, {"symbol": symbol, "interval": interval, "exchange": exchange}).scalar_one() or 0)

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

    def persist_targets(
        self,
        frame: pd.DataFrame,
        specs: tuple[TargetSpec, ...],
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
            for spec in specs:
                class_col = f"{spec.name}_class"
                return_col = f"{spec.name}_exit_return"
                value = getattr(row, return_col, None)
                target_class = getattr(row, class_col, None)
                if _is_missing(value) or _is_missing(target_class):
                    continue
                rows.append(
                    {
                        "candle_id": int(row.id),
                        "target_name": spec.name,
                        "horizon_candles": spec.horizon_candles,
                        "threshold_pct": Decimal(str(spec.take_profit_pct)),
                        "target_value": Decimal(str(float(value))),
                        "target_class": int(target_class),
                    }
                )

        if not rows:
            return 0

        statement = text(
            """
            INSERT INTO crypto_targets (
                candle_id, target_name, horizon_candles,
                threshold_pct, target_value, target_class
            ) VALUES (
                :candle_id, :target_name, :horizon_candles,
                :threshold_pct, :target_value, :target_class
            )
            ON CONFLICT (candle_id, target_name, horizon_candles)
            DO UPDATE SET
                threshold_pct = EXCLUDED.threshold_pct,
                target_value = EXCLUDED.target_value,
                target_class = EXCLUDED.target_class
            """
        )
        with self.engine.begin() as connection:
            connection.execute(statement, rows)
        return len(rows)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (np.floating, float)):
        return bool(np.isnan(value))
    return bool(pd.isna(value))

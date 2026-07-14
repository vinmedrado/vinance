from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .models import PredictionInput


class PredictionRepository:
    def __init__(self, engine: Engine, config: PredictionEngineConfig = DEFAULT_CONFIG) -> None:
        self.engine = engine
        self.config = config

    def ensure_schema(self) -> None:
        query = text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('crypto_candles', 'crypto_features', 'trading_signals')
            """
        )
        with self.engine.connect() as connection:
            tables = {row[0] for row in connection.execute(query)}
        missing = {"crypto_candles", "crypto_features", "trading_signals"}.difference(tables)
        if missing:
            raise RuntimeError(
                "Trading schema is missing required tables: "
                f"{sorted(missing)}. Apply backend/trading/storage/schema.sql before running Prediction Engine V2."
            )

    def load_latest_features(self, *, symbol: str, interval: str) -> PredictionInput:
        query = text(
            """
            SELECT
                c.id AS candle_id,
                c.symbol,
                c.interval,
                c.open_time,
                c.close,
                f.feature_version,
                f.features
            FROM crypto_features f
            JOIN crypto_candles c ON c.id = f.candle_id
            WHERE f.feature_version = :feature_version
              AND c.symbol = :symbol
              AND c.interval = :interval
            ORDER BY c.open_time DESC
            LIMIT 1
            """
        )
        with self.engine.connect() as connection:
            row = connection.execute(
                query,
                {"feature_version": self.config.feature_version, "symbol": symbol, "interval": interval},
            ).mappings().first()
        if row is None:
            raise LookupError(f"No features found for symbol={symbol} interval={interval} version={self.config.feature_version}")
        if row["symbol"] != symbol or row["interval"] != interval or row["feature_version"] != self.config.feature_version:
            raise RuntimeError(
                "Latest feature query returned an inconsistent row: "
                f"symbol={row['symbol']} interval={row['interval']} feature_version={row['feature_version']}"
            )

        features = _as_dict(row["features"])
        return PredictionInput(
            candle_id=int(row["candle_id"]),
            symbol=str(row["symbol"]),
            interval=str(row["interval"]),
            open_time=row["open_time"],
            close=float(row["close"]),
            features=features,
        )

    def trading_signals_supports_prediction_decisions(self) -> bool:
        query = text(
            """
            SELECT pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
              AND rel.relname = 'trading_signals'
              AND con.contype = 'c'
            """
        )
        with self.engine.connect() as connection:
            checks = [str(row[0]) for row in connection.execute(query)]
        joined = "\n".join(checks)
        return "BUY_CANDIDATE" in joined and "AVOID" in joined


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    return dict(value or {})

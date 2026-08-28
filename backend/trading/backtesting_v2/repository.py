from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.trading.paper_trading_v2.models import MarketCandle

from .config import BacktestingConfig
from .models import HistoricalCandle


class BacktestingRepository:
    def __init__(self, engine: Engine, config: BacktestingConfig) -> None:
        self.engine = engine
        self.config = config

    def load_history(self) -> list[HistoricalCandle]:
        query = """
            SELECT
                c.id AS candle_id,
                c.symbol,
                c.interval,
                c.open_time,
                c.open,
                c.high,
                c.low,
                c.close,
                f.features
            FROM crypto_features f
            JOIN crypto_candles c ON c.id = f.candle_id
            WHERE f.feature_version = :feature_version
              AND c.symbol = :symbol
              AND c.interval = :interval
        """
        params: dict[str, Any] = {
            "feature_version": self.config.feature_version,
            "symbol": self.config.symbol,
            "interval": self.config.interval,
        }
        if self.config.exchange:
            query += " AND LOWER(c.exchange) = LOWER(:exchange)\n"
            params["exchange"] = self.config.exchange
        if self.config.start_time is not None:
            query += " AND c.open_time >= :start_time\n"
            params["start_time"] = self.config.start_time
        if self.config.end_time is not None:
            query += " AND c.open_time <= :end_time\n"
            params["end_time"] = self.config.end_time
        query += " ORDER BY c.open_time ASC\n"
        if self.config.max_candles is not None:
            query += " LIMIT :limit\n"
            params["limit"] = self.config.max_candles
        frame = pd.read_sql(text(query), self.engine, params=params)
        records = [_row_to_historical_candle(row) for row in frame.to_dict("records")]
        validate_history(records, min_period_candles=self.config.min_period_candles)
        return records


def validate_history(
    records: list[HistoricalCandle] | tuple[HistoricalCandle, ...],
    *,
    min_period_candles: int = 1,
    min_candles: int | None = None,
) -> None:
    min_required = min_candles if min_candles is not None else min_period_candles
    if not records:
        raise ValueError("Historical period is empty for the configured filters.")
    if len(records) < min_required:
        raise ValueError(f"Historical period has {len(records)} candles; required minimum is {min_required}.")
    last_time = None
    seen: set[int] = set()
    for item in records:
        candle = item.candle
        if candle.candle_id in seen:
            raise ValueError(f"Duplicate candle_id in historical data: {candle.candle_id}")
        seen.add(candle.candle_id)
        if last_time is not None and candle.open_time <= last_time:
            raise ValueError("Historical candles must be strictly ordered by open_time ASC.")
        last_time = candle.open_time


def _row_to_historical_candle(row: dict[str, Any]) -> HistoricalCandle:
    return HistoricalCandle(
        candle=MarketCandle(
            candle_id=int(row["candle_id"]),
            symbol=str(row["symbol"]),
            interval=str(row["interval"]),
            open_time=_as_datetime(row["open_time"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        ),
        features=_as_dict(row["features"]),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    return dict(value or {})


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return pd.Timestamp(value).to_pydatetime()

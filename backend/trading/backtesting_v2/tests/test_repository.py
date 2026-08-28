from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from backend.trading.backtesting_v2.config import BacktestingConfig
from backend.trading.backtesting_v2.repository import BacktestingRepository, validate_history

from .helpers import history


def test_historical_loading_is_ordered_and_does_not_query_targets(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE crypto_candles (id INTEGER, exchange TEXT, symbol TEXT, interval TEXT, open_time TEXT, open REAL, high REAL, low REAL, close REAL)"))
        connection.execute(text("CREATE TABLE crypto_features (candle_id INTEGER, feature_version TEXT, features TEXT)"))
        connection.execute(
            text("INSERT INTO crypto_candles VALUES (:id, 'binance', 'BTCUSDT', '5m', :open_time, 100, 101, 99, 100)"),
            [
                {"id": 2, "open_time": "2026-01-01T00:05:00+00:00"},
                {"id": 1, "open_time": "2026-01-01T00:00:00+00:00"},
            ],
        )
        connection.execute(
            text("INSERT INTO crypto_features VALUES (:candle_id, 'v2', :features)"),
            [{"candle_id": 2, "features": '{"f1": 2, "f2": 3}'}, {"candle_id": 1, "features": '{"f1": 1, "f2": 2}'}],
        )

    loaded = BacktestingRepository(engine, BacktestingConfig(output_root=tmp_path)).load_history()
    assert [item.candle.candle_id for item in loaded] == [1, 2]
    assert loaded[0].features == {"f1": 1, "f2": 2}


def test_history_validation_rejects_empty_duplicate_and_out_of_order() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_history([])
    rows = history(2)
    rows[1] = type(rows[1])(rows[0].candle, rows[1].features)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_history(rows)
    rows = history(2)
    rows[1] = type(rows[1])(
        type(rows[1].candle)(2, "BTCUSDT", "5m", datetime(2025, 1, 1, tzinfo=timezone.utc), 100, 100, 100, 100),
        rows[1].features,
    )
    with pytest.raises(ValueError, match="ordered"):
        validate_history(rows)

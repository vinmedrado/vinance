from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


class CandleRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def upsert_dataframe(self, dataframe: pd.DataFrame) -> int:
        if dataframe.empty:
            return 0
        rows = dataframe.to_dict(orient="records")
        statement = text("""
            INSERT INTO crypto_candles (
                exchange, symbol, interval, open_time, close_time,
                open, high, low, close, volume, quote_volume, trades
            ) VALUES (
                :exchange, :symbol, :interval, :open_time, :close_time,
                :open, :high, :low, :close, :volume, :quote_volume, :trades
            )
            ON CONFLICT (exchange, symbol, interval, open_time)
            DO UPDATE SET
                close_time = EXCLUDED.close_time,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                quote_volume = EXCLUDED.quote_volume,
                trades = EXCLUDED.trades,
                updated_at = NOW();
        """)
        with self.engine.begin() as connection:
            connection.execute(statement, rows)
        return len(rows)

    def load(self, symbol: str, interval: str, limit: int = 10000) -> pd.DataFrame:
        query = text("""
            SELECT *
            FROM crypto_candles
            WHERE symbol = :symbol AND interval = :interval
            ORDER BY open_time DESC
            LIMIT :limit
        """)
        data = pd.read_sql(query, self.engine, params={"symbol": symbol, "interval": interval, "limit": limit})
        return data.sort_values("open_time").reset_index(drop=True)

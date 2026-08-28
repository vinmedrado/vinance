from __future__ import annotations

from datetime import datetime

import httpx
import pandas as pd

from .base import MarketDataProvider


class BinancePublicProvider(MarketDataProvider):
    BASE_URL = "https://api.binance.com"

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        params: dict[str, object] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(max(limit, 1), 1000),
        }
        if start:
            params["startTime"] = int(start.timestamp() * 1000)
        if end:
            params["endTime"] = int(end.timestamp() * 1000)

        response = httpx.get(f"{self.BASE_URL}/api/v3/klines", params=params, timeout=30)
        response.raise_for_status()
        raw = response.json()
        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ]
        frame = pd.DataFrame(raw, columns=columns)
        if frame.empty:
            return frame
        frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
        for column in ["open", "high", "low", "close", "volume", "quote_volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["trades"] = pd.to_numeric(frame["trades"], errors="coerce").astype("Int64")
        frame["exchange"] = "binance"
        frame["symbol"] = symbol.upper()
        frame["interval"] = interval
        return frame[[
            "exchange", "symbol", "interval", "open_time", "close_time",
            "open", "high", "low", "close", "volume", "quote_volume", "trades",
        ]]

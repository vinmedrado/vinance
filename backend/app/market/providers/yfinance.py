from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

import httpx

from backend.app.core.logging import get_logger
from backend.app.market.schemas import normalize_market, normalize_ticker

logger = get_logger(__name__)


class YFinanceProvider:
    """Yahoo chart API provider without scraping HTML pages."""

    source = "yahoo_finance"

    def __init__(self, timeout: float = 12.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    async def fetch_historical_prices(
        self,
        *,
        ticker: str,
        market: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        normalized_ticker = normalize_ticker(ticker)
        normalized_market = normalize_market(market)
        yahoo_symbol = self._to_yahoo_symbol(normalized_ticker, normalized_market)
        period1 = int(datetime.combine(start, time.min, tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(end, time.min, tzinfo=timezone.utc).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {"period1": period1, "period2": period2, "interval": "1d", "events": "history"}
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                return self._normalize_chart_payload(payload, ticker=normalized_ticker, market=normalized_market)
            except Exception as exc:
                logger.warning("YFinance provider failed", extra={"ticker": normalized_ticker, "attempt": attempt + 1, "error": str(exc)})
                if attempt >= self.retries:
                    return []
                await asyncio.sleep(0.5 * (attempt + 1))
        return []

    def _to_yahoo_symbol(self, ticker: str, market: str) -> str:
        if market in {"acoes", "fii", "etf", "bdr"} and not ticker.endswith(".SA"):
            return f"{ticker}.SA"
        return ticker

    def _normalize_chart_payload(self, payload: dict[str, Any], *, ticker: str, market: str) -> list[dict[str, Any]]:
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            return []
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []
        rows: list[dict[str, Any]] = []
        for index, ts in enumerate(timestamps):
            close = _decimal_or_none(_safe_get(closes, index))
            if close is None:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "market": market,
                    "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                    "open": _decimal_or_none(_safe_get(opens, index)),
                    "high": _decimal_or_none(_safe_get(highs, index)),
                    "low": _decimal_or_none(_safe_get(lows, index)),
                    "close": close,
                    "volume": _decimal_or_none(_safe_get(volumes, index)),
                    "source": self.source,
                }
            )
        return rows


def _safe_get(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None

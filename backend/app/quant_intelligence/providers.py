from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class MarketQuote:
    ticker: str
    price: float | None = None
    currency: str | None = None
    change_pct_30d: float | None = None
    volatility_90d: float | None = None
    source: str = "fallback"
    retrieved_at: str = datetime.now(timezone.utc).isoformat()


def _yf_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if t in {"SELIC", "CDB", "IPCA+"}:
        return t
    if t.endswith(".SA") or "-" in t or t.endswith("=X"):
        return t
    # B3 tickers normally need .SA on Yahoo Finance.
    if any(t.endswith(suffix) for suffix in ["11", "3", "4", "5", "6"]):
        return f"{t}.SA"
    return t


def _returns(values: list[float]) -> list[float]:
    out: list[float] = []
    for a, b in zip(values, values[1:]):
        if a and b:
            out.append((b / a) - 1)
    return out


def fetch_yfinance_quote(ticker: str) -> MarketQuote:
    """Fetch a compact quote with safe fallback.

    The function is optional by design: if yfinance/network is unavailable in
    local/Render, the platform remains operational with deterministic fallback
    data instead of breaking the Quant Lab.
    """
    if os.getenv("VINANCE_ENABLE_YFINANCE", "false").lower() not in {"1", "true", "yes", "on"}:
        return MarketQuote(ticker=ticker, source="disabled")

    try:
        import yfinance as yf  # type: ignore

        symbol = _yf_symbol(ticker)
        if symbol == ticker and ticker in {"SELIC", "CDB", "IPCA+"}:
            return MarketQuote(ticker=ticker, source="fixed_income_policy")
        hist = yf.Ticker(symbol).history(period="6mo", interval="1d", auto_adjust=True)
        if hist is None or hist.empty or "Close" not in hist:
            return MarketQuote(ticker=ticker, source="empty")
        closes = [float(x) for x in hist["Close"].dropna().tolist()]
        if not closes:
            return MarketQuote(ticker=ticker, source="empty")
        last = closes[-1]
        base = closes[-22] if len(closes) >= 22 else closes[0]
        change_30d = (last / base) - 1 if base else None
        daily_returns = _returns(closes[-90:])
        vol_90d = None
        if len(daily_returns) > 2:
            avg = sum(daily_returns) / len(daily_returns)
            std = math.sqrt(sum((x - avg) ** 2 for x in daily_returns) / (len(daily_returns) - 1))
            vol_90d = std * math.sqrt(252)
        return MarketQuote(
            ticker=ticker,
            price=round(last, 4),
            currency="BRL" if symbol.endswith(".SA") else None,
            change_pct_30d=round(change_30d, 4) if change_30d is not None else None,
            volatility_90d=round(vol_90d, 4) if vol_90d is not None else None,
            source="yfinance",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        return MarketQuote(ticker=ticker, source=f"fallback:{exc.__class__.__name__}")


def quote_to_payload(quote: MarketQuote) -> dict[str, Any]:
    return {
        "ticker": quote.ticker,
        "price": quote.price,
        "currency": quote.currency,
        "change_pct_30d": quote.change_pct_30d,
        "volatility_90d": quote.volatility_90d,
        "source": quote.source,
        "retrieved_at": quote.retrieved_at,
    }

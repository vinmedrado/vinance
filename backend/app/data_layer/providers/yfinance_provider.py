from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from backend.app.data_layer.utils.ticker_mapper import to_yfinance_ticker


class YFinanceProvider:
    source = "yfinance"

    def __init__(self) -> None:
        try:
            import yfinance as yf  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Dependência yfinance não está instalada. Rode: pip install yfinance==0.2.51") from exc
        self.yf = yf

    def get_history(self, ticker: str, asset_class: str | None, start: str, end: str | None = None) -> list[dict[str, Any]]:
        yf_ticker = to_yfinance_ticker(ticker, asset_class)
        data = self.yf.download(yf_ticker, start=start, end=end or date.today().isoformat(), progress=False, auto_adjust=False, threads=False)
        if data is None or len(data) == 0:
            return []
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]
        data = data.reset_index()
        rows: list[dict[str, Any]] = []
        for _, item in data.iterrows():
            dt = item.get("Date")
            if pd.isna(dt):
                continue
            rows.append(
                {
                    "date": pd.to_datetime(dt).date().isoformat(),
                    "open": _safe_float(item.get("Open")),
                    "high": _safe_float(item.get("High")),
                    "low": _safe_float(item.get("Low")),
                    "close": _safe_float(item.get("Close")),
                    "adjusted_close": _safe_float(item.get("Adj Close")),
                    "volume": _safe_float(item.get("Volume")),
                    "source": self.source,
                    "raw_json": {"yf_ticker": yf_ticker},
                }
            )
        return rows

    def get_dividends(self, ticker: str, asset_class: str | None) -> list[dict[str, Any]]:
        yf_ticker = to_yfinance_ticker(ticker, asset_class)
        series = self.yf.Ticker(yf_ticker).dividends
        if series is None or len(series) == 0:
            return []
        rows: list[dict[str, Any]] = []
        for dt, amount in series.items():
            rows.append(
                {
                    "date": pd.to_datetime(dt).date().isoformat(),
                    "ex_date": pd.to_datetime(dt).date().isoformat(),
                    "payment_date": None,
                    "amount": _safe_float(amount),
                    "source": self.source,
                    "raw_json": {"yf_ticker": yf_ticker},
                }
            )
        return rows


def _safe_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None

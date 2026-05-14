from __future__ import annotations

BRAZIL_CLASSES = {"ACAO", "FII", "ETF", "BDR", "EQUITY", "FII", "ETF", "BDR"}

INDEX_TICKERS = {
    "IBOV": "^BVSP",
    "IFIX": "^IFIX",
    "S&P500": "^GSPC",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOLAR": "BRL=X",
}


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def to_yfinance_ticker(ticker: str, asset_class: str | None = None) -> str:
    ticker = normalize_ticker(ticker)
    asset_class = (asset_class or "").strip().upper()
    if ticker in INDEX_TICKERS:
        return INDEX_TICKERS[ticker]
    if ticker.endswith(".SA"):
        return ticker
    if asset_class in BRAZIL_CLASSES:
        return f"{ticker}.SA"
    return ticker


def index_to_yfinance(symbol: str) -> str:
    return INDEX_TICKERS.get(normalize_ticker(symbol), normalize_ticker(symbol))

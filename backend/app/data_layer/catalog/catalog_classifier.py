from __future__ import annotations

import re

ALLOWED_ASSET_CLASSES = {
    "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity", "fixed_income", "unknown",
}
LEGACY_TO_CANONICAL = {
    "ACAO": "equity", "AÇÃO": "equity", "ACOES": "equity", "AÇÕES": "equity",
    "FII": "fii", "ETF": "etf", "BDR": "bdr", "CRIPTO": "crypto", "CRYPTO": "crypto",
    "INDICE": "index", "ÍNDICE": "index", "INDEX": "index", "MOEDA": "currency", "CURRENCY": "currency",
}
INDEX_TICKERS = {"IBOV", "IFIX", "SMLL", "IDIV", "S&P500", "SP500", "NASDAQ", "DOWJONES", "DOLAR"}
CURRENCY_TICKERS = {"USD-BRL", "EUR-BRL", "GBP-BRL", "JPY-BRL", "DOLAR", "BRL=X"}
COMMODITY_TICKERS = {"GC=F", "SI=F", "CL=F", "BZ=F", "KC=F", "SB=F"}
ETF_11_HINTS = {"IVVB11", "BOVA11", "SMAL11", "HASH11", "NASD11", "DIVO11", "XFIX11", "SPXI11", "BOVV11", "ECOO11", "GOVE11", "MATB11", "PIBB11", "XBOV11", "ESGB11", "TECK11", "USTK11", "WRLD11", "GOLD11", "GENB11"}


def normalize_ticker(ticker: str | None) -> str:
    return (ticker or "").strip().upper()


def normalize_asset_class(asset_class: str | None) -> str:
    value = (asset_class or "").strip()
    if not value:
        return "unknown"
    upper = value.upper()
    canonical = LEGACY_TO_CANONICAL.get(upper, value.lower())
    return canonical if canonical in ALLOWED_ASSET_CLASSES else "unknown"


def classify_asset(ticker: str, name: str | None = None, asset_class: str | None = None) -> str:
    explicit = normalize_asset_class(asset_class)
    if explicit != "unknown":
        return explicit
    t = normalize_ticker(ticker)
    if not t:
        return "unknown"
    if t in INDEX_TICKERS or t.startswith("^"):
        return "index"
    if t in CURRENCY_TICKERS or re.match(r"^[A-Z]{3}-[A-Z]{3}$", t):
        return "currency"
    if t in COMMODITY_TICKERS:
        return "commodity"
    if re.match(r"^[A-Z0-9]+-USD$", t):
        return "crypto"
    if re.match(r"^[A-Z]{4}(34|35|39)$", t):
        return "bdr"
    if t in ETF_11_HINTS:
        return "etf"
    if re.match(r"^[A-Z]{4}11$", t):
        text = (name or "").lower()
        if "etf" in text or "índice" in text or "indice" in text:
            return "etf"
        return "fii"
    if re.match(r"^[A-Z]{4}[3-6]$", t) or re.match(r"^[A-Z]{4}11$", t):
        return "equity"
    return "unknown"


def valid_ticker(ticker: str) -> bool:
    return bool(re.match(r"^[A-Z0-9\-\.\^=&]+$", normalize_ticker(ticker)))

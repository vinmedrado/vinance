"""FinanceOS PATCH 7 catalog package.

Compatibility exports keep PATCH 6 scripts working while the new catalog modules
live under backend.app.data_layer.catalog/.
"""

CATALOG_ASSETS = [
    {"ticker": "PETR4", "name": "Petrobras PN", "asset_class": "equity", "country": "BR", "currency": "BRL"},
    {"ticker": "MXRF11", "name": "MXRF11 Fundo Imobiliário", "asset_class": "fii", "country": "BR", "currency": "BRL"},
    {"ticker": "IVVB11", "name": "IVVB11 ETF Brasil", "asset_class": "etf", "country": "BR", "currency": "BRL"},
]

MARKET_INDICES = [
    {"symbol": "IBOV", "name": "Índice Bovespa", "source_symbol": "^BVSP"},
    {"symbol": "IFIX", "name": "Índice de Fundos Imobiliários", "source_symbol": "^IFIX"},
    {"symbol": "S&P500", "name": "S&P 500", "source_symbol": "^GSPC"},
    {"symbol": "NASDAQ", "name": "Nasdaq Composite", "source_symbol": "^IXIC"},
    {"symbol": "DOLAR", "name": "Dólar / Real", "source_symbol": "BRL=X"},
]

BCB_SGS_INDICATORS = {
    "selic": 432,
    "cdi": 12,
    "ipca": 433,
    "igpm": 189,
    "dolar": 1,
}
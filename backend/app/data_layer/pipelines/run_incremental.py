from __future__ import annotations

from backend.app.data_layer.pipelines import assets_catalog, dividends, historical_prices, indices, macro


def run() -> dict:
    results = {
        "assets_catalog": assets_catalog.run(),
        "historical_prices": historical_prices.run(incremental=True),
        "dividends": dividends.run(),
        "macro_indicators": macro.run(),
        "market_indices": indices.run(incremental=True),
    }
    return results

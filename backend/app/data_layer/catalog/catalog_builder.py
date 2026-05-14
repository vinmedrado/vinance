from __future__ import annotations

from backend.app.data_layer.catalog.catalog_classifier import classify_asset
from backend.app.data_layer.catalog.catalog_quality import validate_catalog_items
from backend.app.data_layer.catalog.catalog_repository import upsert_many
from backend.app.data_layer.catalog.catalog_sources import load_catalog

VALID_SOURCES = {"all", "fallback", "yfinance", "b3"}
VALID_CLASSES = {"all", "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity"}


def build_massive_catalog(source: str = "all", asset_class: str = "all", limit: int | None = None) -> list[dict]:
    source = (source or "all").lower()
    asset_class = (asset_class or "all").lower()
    if source not in VALID_SOURCES:
        raise ValueError(f"source inválido: {source}. Use: {', '.join(sorted(VALID_SOURCES))}")
    if asset_class not in VALID_CLASSES:
        raise ValueError(f"asset-class inválido: {asset_class}. Use: {', '.join(sorted(VALID_CLASSES))}")
    rows = [asset.as_dict() for asset in load_catalog(source=source, asset_class=asset_class, limit=limit)]
    for row in rows:
        row["asset_class"] = classify_asset(row["ticker"], row.get("name"), row.get("asset_class"))
    return rows


def sync_massive_catalog(source: str = "all", asset_class: str = "all", limit: int | None = None, dry_run: bool = False) -> dict:
    rows = build_massive_catalog(source=source, asset_class=asset_class, limit=limit)
    quality = validate_catalog_items(rows)
    invalid = len(quality["invalid_rows"])
    valid_tickers = {item["ticker"] for item in quality["invalid_rows"]}
    valid_rows = [row for row in rows if row.get("ticker") not in valid_tickers]
    result = upsert_many(valid_rows, dry_run=dry_run)
    return {
        "source": source,
        "asset_class": asset_class,
        "dry_run": dry_run,
        "loaded": len(rows),
        "valid": len(valid_rows),
        "invalid": invalid,
        **result,
        "quality": quality,
    }

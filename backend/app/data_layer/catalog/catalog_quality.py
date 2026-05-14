from __future__ import annotations

from collections import Counter
from typing import Iterable

from backend.app.data_layer.catalog.catalog_classifier import ALLOWED_ASSET_CLASSES, classify_asset, normalize_asset_class, normalize_ticker, valid_ticker

REQUIRED_FIELDS = ["ticker", "name", "asset_class", "country", "currency"]


def validate_catalog_items(items: Iterable[dict]) -> dict:
    rows = list(items)
    errors: list[str] = []
    tickers = [normalize_ticker(str(item.get("ticker", ""))) for item in rows]
    counts = Counter(tickers)
    duplicates = sorted([ticker for ticker, count in counts.items() if ticker and count > 1])
    for dup in duplicates:
        errors.append(f"ticker duplicado: {dup}")
    invalid_rows = []
    for idx, item in enumerate(rows, start=1):
        ticker = normalize_ticker(str(item.get("ticker", "")))
        asset_class = normalize_asset_class(str(item.get("asset_class", "unknown")))
        row_errors = []
        for field in REQUIRED_FIELDS:
            if not str(item.get(field, "")).strip():
                row_errors.append(f"{field} vazio")
        if ticker and not valid_ticker(ticker):
            row_errors.append("ticker inválido")
        if asset_class not in ALLOWED_ASSET_CLASSES:
            row_errors.append("asset_class inválida")
        if classify_asset(ticker, item.get("name"), asset_class) == "unknown":
            row_errors.append("ativo desconhecido")
        if row_errors:
            invalid_rows.append({"row": idx, "ticker": ticker, "errors": row_errors})
    return {
        "total": len(rows),
        "duplicates": duplicates,
        "invalid_rows": invalid_rows,
        "errors": errors,
        "is_valid": not duplicates and not invalid_rows,
    }


def summarize_assets(rows: Iterable[dict]) -> dict:
    items = list(rows)
    by_class = Counter(normalize_asset_class(str(item.get("asset_class") or "unknown")) for item in items)
    by_country = Counter(str(item.get("country") or "UNKNOWN").upper() for item in items)
    required_coverage = {}
    for field in REQUIRED_FIELDS:
        filled = sum(1 for item in items if str(item.get(field, "")).strip())
        required_coverage[field] = {"filled": filled, "missing": len(items) - filled}
    unknown = sum(1 for item in items if normalize_asset_class(str(item.get("asset_class") or "unknown")) == "unknown")
    return {
        "total_assets": len(items),
        "by_class": dict(sorted(by_class.items())),
        "by_country": dict(sorted(by_country.items())),
        "unknown_assets": unknown,
        "required_coverage": required_coverage,
    }

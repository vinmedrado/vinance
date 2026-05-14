from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FALLBACK_DIR = PROJECT_ROOT / "data" / "catalog_fallback"
FALLBACK_FILES = [
    "brazil_equities.csv", "brazil_fiis.csv", "brazil_etfs.csv", "brazil_bdrs.csv",
    "indices.csv", "crypto.csv", "currencies.csv", "commodities.csv", "global_equities.csv", "global_etfs.csv",
]


@dataclass(frozen=True)
class CatalogAsset:
    ticker: str
    name: str
    asset_class: str
    country: str
    exchange: str
    currency: str
    source: str = "fallback"
    is_active: bool = True

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker, "symbol": self.ticker, "name": self.name, "asset_class": self.asset_class,
            "country": self.country, "exchange": self.exchange, "currency": self.currency,
            "source": self.source, "is_active": int(self.is_active),
        }


def load_fallback_assets(asset_class: str = "all", limit: int | None = None) -> list[CatalogAsset]:
    assets: list[CatalogAsset] = []
    for filename in FALLBACK_FILES:
        path = FALLBACK_DIR / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                item = CatalogAsset(
                    ticker=(row.get("ticker") or "").strip().upper(),
                    name=(row.get("name") or "").strip(),
                    asset_class=(row.get("asset_class") or "unknown").strip().lower(),
                    country=(row.get("country") or "").strip().upper(),
                    exchange=(row.get("exchange") or "").strip().upper(),
                    currency=(row.get("currency") or "").strip().upper(),
                    source="fallback",
                    is_active=True,
                )
                if asset_class != "all" and item.asset_class != asset_class:
                    continue
                assets.append(item)
                if limit and len(assets) >= limit:
                    return assets
    return assets


def load_yfinance_discovery(asset_class: str = "all", limit: int | None = None) -> list[CatalogAsset]:
    # yfinance does not expose a stable full-market discovery API. Keep this intentionally conservative
    # and backed by the local fallback catalog so the pipeline remains deterministic and offline-safe.
    return load_fallback_assets(asset_class=asset_class, limit=limit)


def load_b3_discovery(asset_class: str = "all", limit: int | None = None) -> list[CatalogAsset]:
    # B3 public lists change format frequently. PATCH 7 keeps a versioned fallback first, without scraping.
    br_classes = {"equity", "fii", "etf", "bdr", "index", "currency"}
    items = [asset for asset in load_fallback_assets("all", None) if asset.asset_class in br_classes]
    if asset_class != "all":
        items = [asset for asset in items if asset.asset_class == asset_class]
    return items[:limit] if limit else items


def load_catalog(source: str = "all", asset_class: str = "all", limit: int | None = None) -> list[CatalogAsset]:
    source = (source or "all").lower()
    asset_class = (asset_class or "all").lower()
    loaders = []
    if source in {"all", "fallback"}:
        loaders.append(load_fallback_assets)
    if source in {"all", "yfinance"}:
        loaders.append(load_yfinance_discovery)
    if source in {"all", "b3"}:
        loaders.append(load_b3_discovery)
    seen: set[str] = set()
    output: list[CatalogAsset] = []
    for loader in loaders:
        for asset in loader(asset_class=asset_class, limit=None):
            key = asset.ticker.upper()
            if key in seen:
                continue
            seen.add(key)
            output.append(asset)
            if limit and len(output) >= limit:
                return output
    return output

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.core.logging import get_logger
from backend.app.market import service as market_service
from backend.app.market.providers.coingecko import CoinGeckoClient

logger = get_logger(__name__)

MAX_BATCH_SIZE = 500
PROVIDER_BATCH_SIZE = 50


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def coin_id_for_asset(asset: AssetCatalog) -> str:
    return str(asset.ticker or "").strip().lower()


def normalize_coingecko_market_data(payload: list[dict[str, Any]], *, ticker_by_coin_id: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    today = datetime.now(timezone.utc).date()
    prices: list[dict[str, Any]] = []
    fundamentals: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        coin_id = str(row.get("id") or "").strip().lower()
        ticker = ticker_by_coin_id.get(coin_id, str(row.get("symbol") or "").strip().upper())
        if not coin_id or not ticker:
            continue
        price_usd = _decimal(row.get("current_price"))
        if price_usd and price_usd > 0:
            prices.append(
                {
                    "ticker": ticker.upper(),
                    "market": "cripto",
                    "date": today,
                    "open": None,
                    "high": _decimal(row.get("high_24h")),
                    "low": _decimal(row.get("low_24h")),
                    "close": price_usd,
                    "volume": _decimal(row.get("total_volume")),
                    "source": "coingecko",
                }
            )
        fundamentals.append(
            {
                "coin_id": coin_id,
                "ticker": ticker.upper(),
                "name": str(row.get("name") or ticker.upper()),
                "date": today,
                "price_brl": None,
                "price_usd": price_usd,
                "market_cap_usd": _decimal(row.get("market_cap")),
                "market_cap_rank": row.get("market_cap_rank"),
                "volume_24h_usd": _decimal(row.get("total_volume")),
                "price_change_1h_pct": _decimal(row.get("price_change_percentage_1h_in_currency")),
                "price_change_24h_pct": _decimal(row.get("price_change_percentage_24h_in_currency") or row.get("price_change_percentage_24h")),
                "price_change_7d_pct": _decimal(row.get("price_change_percentage_7d_in_currency")),
                "price_change_30d_pct": _decimal(row.get("price_change_percentage_30d_in_currency")),
                "price_change_90d_pct": _decimal(row.get("price_change_percentage_90d_in_currency")),
                "price_change_1y_pct": _decimal(row.get("price_change_percentage_1y_in_currency")),
                "circulating_supply": _decimal(row.get("circulating_supply")),
                "max_supply": _decimal(row.get("max_supply")),
                "ath_price_usd": _decimal(row.get("ath")),
                "ath_change_pct": _decimal(row.get("ath_change_percentage")),
                "source": "coingecko",
            }
        )
    return prices, fundamentals


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def load_crypto_catalog_assets(session: AsyncSession, *, limit: int | None = None) -> list[AssetCatalog]:
    query = (
        select(AssetCatalog)
        .where(AssetCatalog.is_active.is_(True), AssetCatalog.market == "cripto")
        .order_by(AssetCatalog.ticker.asc())
    )
    if limit:
        query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def sync_crypto_market_from_catalog(
    session: AsyncSession,
    *,
    client: CoinGeckoClient | None = None,
    batch_size: int = PROVIDER_BATCH_SIZE,
    limit_assets: int | None = None,
) -> dict[str, int]:
    client = client or CoinGeckoClient()
    assets = await load_crypto_catalog_assets(session, limit=limit_assets)
    summary = {"assets": len(assets), "prices_processed": 0, "fundamentals_processed": 0, "inserted": 0, "updated": 0, "failed_batches": 0}
    for batch in _chunks(assets, max(1, min(batch_size, MAX_BATCH_SIZE))):
        coin_ids = [coin_id_for_asset(asset) for asset in batch]
        ticker_by_coin_id = {coin_id_for_asset(asset): asset.ticker.upper() for asset in batch}
        payload = await client.get_market_data(coin_ids)
        if not payload:
            summary["failed_batches"] += 1
            continue
        prices, fundamentals = normalize_coingecko_market_data(payload, ticker_by_coin_id=ticker_by_coin_id)
        price_summary = await market_service.bulk_upsert_asset_prices(session, prices=prices, batch_size=MAX_BATCH_SIZE)
        summary["prices_processed"] += price_summary["processed"]
        summary["inserted"] += price_summary["inserted"]
        summary["updated"] += price_summary["updated"]
        for item in fundamentals[:MAX_BATCH_SIZE]:
            await market_service.upsert_cripto_fundamental(session, item)
            summary["fundamentals_processed"] += 1
        await asyncio.sleep(1.0)
    logger.info("CoinGecko crypto sync finished", extra=summary)
    return summary

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.app.catalog.models import AssetCatalog
from backend.app.core.celery import celery_app
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.logging import get_logger
from backend.app.market.providers.bcb import BCBProvider
from backend.app.market.providers.tesouro import TesouroDiretoProvider
from backend.app.market.providers.yfinance import YFinanceProvider
from backend.app.market import service

logger = get_logger(__name__)


@celery_app.task(name="market.sync_macro_indicators", queue="market")
def sync_macro_indicators() -> dict[str, int]:
    return asyncio.run(_sync_macro_indicators())


async def _sync_macro_indicators() -> dict[str, int]:
    provider = BCBProvider()
    rows = await provider.fetch_initial_indicators()
    async with AsyncSessionLocal() as session:
        processed = 0
        for row in rows:
            await service.upsert_macro_indicator(session, payload=row)
            processed += 1
    logger.info("Macro indicators synced", extra={"processed": processed})
    return {"processed": processed}


@celery_app.task(name="market.sync_tesouro_direto", queue="market")
def sync_tesouro_direto() -> dict[str, int]:
    return asyncio.run(_sync_tesouro_direto())


async def _sync_tesouro_direto() -> dict[str, int]:
    provider = TesouroDiretoProvider()
    rows = await provider.fetch_produtos()
    async with AsyncSessionLocal() as session:
        processed = 0
        for row in rows:
            await service.upsert_renda_fixa_produto(session, payload=row)
            processed += 1
    logger.info("Tesouro Direto products synced", extra={"processed": processed})
    return {"processed": processed}


@celery_app.task(name="market.sync_historical_prices_weekly", queue="market")
def sync_historical_prices_weekly(days: int = 30, limit_assets: int = 200) -> dict[str, int]:
    return asyncio.run(_sync_historical_prices_weekly(days=days, limit_assets=limit_assets))


async def _sync_historical_prices_weekly(*, days: int, limit_assets: int) -> dict[str, int]:
    provider = YFinanceProvider()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AssetCatalog)
            .where(AssetCatalog.is_active.is_(True), AssetCatalog.market.in_(["acoes", "fii", "etf", "bdr", "cripto"]))
            .order_by(AssetCatalog.market.asc(), AssetCatalog.ticker.asc())
            .limit(limit_assets)
        )
        assets = list(result.scalars().all())
        processed = 0
        inserted = 0
        updated = 0
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)
        for asset in assets:
            rows = await provider.fetch_historical_prices(ticker=asset.ticker, market=asset.market, start=start, end=end)
            summary = await service.bulk_upsert_asset_prices(session, prices=rows)
            processed += summary["processed"]
            inserted += summary["inserted"]
            updated += summary["updated"]
    logger.info("Historical prices synced", extra={"assets": len(assets), "processed": processed})
    return {"assets": len(assets), "processed": processed, "inserted": inserted, "updated": updated}


@celery_app.task(name="market.cleanup_old_asset_prices", queue="market")
def cleanup_old_asset_prices() -> dict[str, int]:
    return asyncio.run(_cleanup_old_asset_prices())


async def _cleanup_old_asset_prices() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        deleted = await service.cleanup_asset_prices_older_than_2_years(session)
    logger.info("Old asset prices cleaned", extra={"deleted": deleted})
    return {"deleted": deleted}

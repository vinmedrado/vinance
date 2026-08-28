from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.catalog.schemas import AssetCatalogCreate, AssetCatalogUpdate, normalize_market, normalize_ticker


async def create_asset(session: AsyncSession, *, payload: AssetCatalogCreate) -> AssetCatalog:
    asset = AssetCatalog(**payload.normalized_payload())
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


async def get_asset_by_ticker_and_market(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
    include_inactive: bool = False,
) -> AssetCatalog | None:
    query = select(AssetCatalog).where(
        AssetCatalog.ticker == normalize_ticker(ticker),
        AssetCatalog.market == normalize_market(market),
    )
    if not include_inactive:
        query = query.where(AssetCatalog.is_active.is_(True))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_assets(
    session: AsyncSession,
    *,
    market: str | None = None,
    is_active: bool | None = True,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AssetCatalog], int]:
    filters = []
    if market is not None:
        filters.append(AssetCatalog.market == normalize_market(market))
    if is_active is not None:
        filters.append(AssetCatalog.is_active.is_(is_active))
    if search:
        term = f"%{search.strip().upper()}%"
        filters.append(or_(AssetCatalog.ticker.ilike(term), AssetCatalog.name.ilike(f"%{search.strip()}%")))

    base_query = select(AssetCatalog).where(*filters)
    count_query = select(func.count()).select_from(AssetCatalog).where(*filters)

    total_result = await session.execute(count_query)
    total = int(total_result.scalar_one() or 0)

    result = await session.execute(
        base_query.order_by(AssetCatalog.market.asc(), AssetCatalog.ticker.asc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_asset(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
    payload: AssetCatalogUpdate,
) -> AssetCatalog | None:
    asset = await get_asset_by_ticker_and_market(session, ticker=ticker, market=market, include_inactive=True)
    if asset is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(asset, field, value)
    await session.commit()
    await session.refresh(asset)
    return asset


async def deactivate_asset(session: AsyncSession, *, ticker: str, market: str) -> AssetCatalog | None:
    asset = await get_asset_by_ticker_and_market(session, ticker=ticker, market=market, include_inactive=True)
    if asset is None:
        return None
    asset.is_active = False
    await session.commit()
    await session.refresh(asset)
    return asset

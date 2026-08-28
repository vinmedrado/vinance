from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.catalog import service
from backend.app.catalog.schemas import (
    AssetCatalogCreate,
    AssetCatalogListResponse,
    AssetCatalogRead,
    AssetCatalogUpdate,
    AssetMarket,
)
from backend.app.core.database import get_session

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=AssetCatalogListResponse)
async def list_catalog(
    market: AssetMarket | None = None,
    is_active: bool | None = True,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_assets(
        session,
        market=market,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )
    return AssetCatalogListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{market}/{ticker}", response_model=AssetCatalogRead)
async def get_catalog_asset(
    market: AssetMarket,
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    asset = await service.get_asset_by_ticker_and_market(session, ticker=ticker, market=market)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.post("", response_model=AssetCatalogRead, status_code=status.HTTP_201_CREATED)
async def create_catalog_asset(
    payload: AssetCatalogCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _ = current_user
    try:
        return await service.create_asset(session, payload=payload)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Asset already exists for market") from exc


@router.put("/{market}/{ticker}", response_model=AssetCatalogRead)
async def update_catalog_asset(
    market: AssetMarket,
    ticker: str,
    payload: AssetCatalogUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _ = current_user
    asset = await service.update_asset(session, ticker=ticker, market=market, payload=payload)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.delete("/{market}/{ticker}", response_model=AssetCatalogRead)
async def deactivate_catalog_asset(
    market: AssetMarket,
    ticker: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _ = current_user
    asset = await service.deactivate_asset(session, ticker=ticker, market=market)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset

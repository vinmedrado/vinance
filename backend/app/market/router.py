from __future__ import annotations

from datetime import date
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.market import service
from backend.app.market.schemas import (
    AcaoFundamentalListResponse,
    AssetPriceListResponse,
    BdrFundamentalListResponse,
    CriptoFundamentalListResponse,
    EtfFundamentalListResponse,
    FiiFundamentalListResponse,
    MacroCode,
    MacroIndicatorListResponse,
    MarketCode,
    RendaFixaListResponse,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/macro", response_model=MacroIndicatorListResponse)
async def get_macro_indicators(
    code: MacroCode | None = None,
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_macro_indicators(session, code=code)
    return MacroIndicatorListResponse(items=items, total=total)


@router.get("/prices/{market}/{ticker}", response_model=AssetPriceListResponse)
async def get_asset_prices(
    market: MarketCode,
    ticker: str,
    limit: int = Query(default=365, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_asset_prices(session, market=market, ticker=ticker, limit=limit, offset=offset)
    return AssetPriceListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/renda-fixa", response_model=RendaFixaListResponse)
async def get_renda_fixa(
    is_active: bool = True,
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_renda_fixa_produtos(session, is_active=is_active)
    return RendaFixaListResponse(items=items, total=total)


async def _fundamentals_response(
    session: AsyncSession,
    listing_fn: Callable[..., Awaitable[tuple[list, int]]],
    response_model,
    *,
    ticker: str | None,
    date_from: date | None,
    date_to: date | None,
    source: str | None,
    limit: int,
    offset: int,
):
    items, total = await listing_fn(
        session,
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
        source=source,
        limit=limit,
        offset=offset,
    )
    return response_model(items=items, total=total, limit=limit, offset=offset)


@router.get("/fundamentals/fii", response_model=FiiFundamentalListResponse)
async def get_fii_fundamentals(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await _fundamentals_response(session, service.list_fii_fundamentals, FiiFundamentalListResponse, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


@router.get("/fundamentals/acoes", response_model=AcaoFundamentalListResponse)
async def get_acoes_fundamentals(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await _fundamentals_response(session, service.list_acoes_fundamentals, AcaoFundamentalListResponse, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


@router.get("/fundamentals/etf", response_model=EtfFundamentalListResponse)
async def get_etf_fundamentals(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await _fundamentals_response(session, service.list_etf_fundamentals, EtfFundamentalListResponse, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


@router.get("/fundamentals/bdr", response_model=BdrFundamentalListResponse)
async def get_bdr_fundamentals(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await _fundamentals_response(session, service.list_bdr_fundamentals, BdrFundamentalListResponse, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


@router.get("/fundamentals/cripto", response_model=CriptoFundamentalListResponse)
async def get_cripto_fundamentals(
    ticker: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await _fundamentals_response(session, service.list_cripto_fundamentals, CriptoFundamentalListResponse, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)

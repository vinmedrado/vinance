from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.market.services.market_data_service import MarketDataService
from backend.app.data_layer.pipelines import assets_catalog as data_assets_catalog
from backend.app.data_layer.pipelines import dividends as data_dividends
from backend.app.data_layer.pipelines import historical_prices as data_historical_prices
from backend.app.data_layer.pipelines import indices as data_indices
from backend.app.data_layer.pipelines import macro as data_macro
from backend.app.data_layer.pipelines import run_full as data_run_full

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/assets")
def assets(search: str | None = Query(default=None, max_length=80), db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return {"assets": MarketDataService(db).get_assets(search=search)}


@router.get("/prices")
def prices(symbols: str = Query(..., min_length=1, max_length=500), db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    tickers = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return {"results": MarketDataService(db).get_b3_quotes(tickers)}


@router.get("/macro")
def macro(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return MarketDataService(db).get_macro_context()


@router.get("/data/dashboard")
def market_data_dashboard(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return MarketDataService(db).dashboard()


@router.post("/data/sync/catalog")
def sync_catalog(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_assets_catalog.run()


@router.post("/data/sync/prices")
def sync_prices(years: int = 5, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_historical_prices.run(incremental=False)


@router.post("/data/sync/dividends")
def sync_divs(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_dividends.run()


@router.post("/data/sync/macro")
def sync_macro(years: int = 5, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_macro.run()


@router.post("/data/sync/indices")
def sync_indices(years: int = 5, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_indices.run(incremental=False)


@router.post("/data/sync/all")
def sync_all(years: int = 5, auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return data_run_full.run()

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.market.models import Asset
from backend.app.investment.models import FixedIncomeProduct, DataSyncLog
from backend.app.financial.services.profile_dashboard import ensure_profile, profile_to_dict
from backend.app.investment.portfolio_allocator import PortfolioAllocator
from backend.app.investment.schemas import AllocationRequest, AssetOut, FixedIncomeImportRequest, SyncResponse, YFinanceSyncRequest
from backend.app.investment.services.analysis_service import InvestmentAnalysisService
from backend.app.investment.services.data_sync_service import DataSyncService

router = APIRouter(prefix="/investments/multiassets", tags=["Investment Multiassets"])


@router.post("/sync/yfinance", response_model=SyncResponse)
def sync_yfinance(payload: YFinanceSyncRequest, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return DataSyncService(db).sync_yfinance(payload.symbols, payload.asset_class, start=payload.start, end=payload.end)


@router.post("/sync/bcb/selic", response_model=SyncResponse)
def sync_bcb_selic(start: date | None = None, end: date | None = None, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return DataSyncService(db).sync_bcb_selic(start=start, end=end)


@router.post("/sync/tesouro", response_model=SyncResponse)
def sync_tesouro(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return DataSyncService(db).sync_tesouro()


@router.post("/fixed-income/import", response_model=SyncResponse)
def import_fixed_income(payload: FixedIncomeImportRequest, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    inserted = updated = 0
    for product in payload.products:
        data = product.model_dump()
        row = db.query(FixedIncomeProduct).filter(
            FixedIncomeProduct.user_id == auth.user_id,
            FixedIncomeProduct.issuer == data["issuer"],
            FixedIncomeProduct.product_type == data["product_type"],
            FixedIncomeProduct.name == data["name"],
            FixedIncomeProduct.maturity_date == data.get("maturity_date"),
        ).first()
        if row is None:
            db.add(FixedIncomeProduct(user_id=auth.user_id, source="manual", raw_json=data, **data))
            inserted += 1
        else:
            for key, value in data.items():
                setattr(row, key, value)
            row.source = "manual"
            row.raw_json = data
            updated += 1
    db.add(DataSyncLog(source="manual", entity="fixed_income_products", status="success", rows_inserted=inserted, rows_updated=updated, message="Produtos de renda fixa importados manualmente pelo usuário."))
    db.commit()
    return {"status": "success", "inserted": inserted, "updated": updated, "skipped": 0, "warnings": []}


@router.get("/assets", response_model=list[AssetOut])
def list_assets(asset_class: str | None = None, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    query = db.query(Asset).order_by(Asset.updated_at.desc())
    if asset_class:
        query = query.filter(Asset.asset_class == asset_class.lower())
    return [{
        "symbol": row.symbol,
        "name": row.name,
        "asset_class": row.asset_class,
        "source": row.source,
        "currency": row.currency,
        "country": getattr(row, "country", None),
        "last_updated_at": row.last_updated_at.isoformat() if getattr(row, "last_updated_at", None) else None,
        "metadata": row.metadata_json or {},
    } for row in query.limit(500).all()]


@router.get("/analyze/{asset_class}")
def analyze_asset_class(asset_class: str, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return InvestmentAnalysisService(db).analyze_asset_class(asset_class)


@router.post("/allocator")
def allocate_portfolio(payload: AllocationRequest, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    profile = ensure_profile(db, auth.user_id)
    return PortfolioAllocator().allocate(
        capital=payload.capital,
        profile=profile.perfil_risco,
        monthly_income=profile.renda_mensal,
        monthly_expenses=profile.despesas_mensais,
        emergency_reserve=profile.reserva_emergencia,
        monthly_debt_payment=payload.monthly_debt_payment,
    )


@router.get("/dashboard")
def multiasset_dashboard(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    profile = ensure_profile(db, auth.user_id)
    allocator = PortfolioAllocator().allocate(
        capital=max(float(profile.meta_investimento_mensal or 0), 0.0),
        profile=profile.perfil_risco,
        monthly_income=profile.renda_mensal,
        monthly_expenses=profile.despesas_mensais,
        emergency_reserve=profile.reserva_emergencia,
    )
    counts = {row.asset_class: count for row, count in []}
    asset_rows = db.query(Asset.asset_class).all()
    counts = {}
    for row in asset_rows:
        counts[row.asset_class] = counts.get(row.asset_class, 0) + 1
    latest_sync = db.query(DataSyncLog).order_by(DataSyncLog.started_at.desc()).limit(10).all()
    return {
        "profile": profile_to_dict(profile),
        "allocator": allocator,
        "asset_counts_by_class": counts,
        "latest_sync_logs": [{"source": row.source, "entity": row.entity, "status": row.status, "message": row.message, "started_at": row.started_at.isoformat() if row.started_at else None} for row in latest_sync],
        "integration": {
            "decision_engine": "O alocador usa perfil financeiro, reserva, renda, despesas e dívidas antes de sugerir distribuição.",
            "risk_engine": "Investimentos aumentam ou reduzem risco conforme reserva, comprometimento de renda e volatilidade da classe.",
            "financing_capacity": "Parcelas futuras reduzem capital disponível e deslocam alocação para caixa/renda fixa.",
        },
    }

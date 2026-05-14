from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.market.models import InvestmentAnalysisHistory, InvestmentOpportunity
from backend.app.market.schemas import RadarRequest, RadarResponse
from backend.app.market.services.radar_service import RadarService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investments", tags=["Investment Radar"])


@router.post("/radar", response_model=RadarResponse)
def radar(
    payload: RadarRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    user_id = auth.user_id
    logger.info("Executando radar de investimentos: user_id=%s amount=%s risk=%s", user_id, payload.amount, payload.risk_profile)
    return RadarService(db).run_radar(
        user_id=user_id,
        amount=payload.amount,
        risk_profile=payload.risk_profile,
        symbols=payload.symbols,
        crypto_ids=payload.crypto_ids,
    )


@router.get("/opportunities")
def opportunities(
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    user_id = auth.user_id
    rows = (
        db.query(InvestmentOpportunity)
        .filter(InvestmentOpportunity.user_id == user_id)
        .order_by(InvestmentOpportunity.created_at.desc())
        .limit(100)
        .all()
    )
    return {"opportunities": [
        {
            "symbol": row.symbol,
            "asset_class": row.asset_class,
            "score": row.score,
            "classification": row.classification,
            "metrics": row.metrics_json or {},
            "rationale": row.rationale,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]}


@router.get("/history")
def history(
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    user_id = auth.user_id
    rows = (
        db.query(InvestmentAnalysisHistory)
        .filter(InvestmentAnalysisHistory.user_id == user_id)
        .order_by(InvestmentAnalysisHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return {"history": [
        {
            "amount": row.amount,
            "risk_profile": row.risk_profile,
            "allocation": row.allocation_json or {},
            "top_opportunities": row.top_opportunities_json or [],
            "macro_context": row.macro_context_json or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]}

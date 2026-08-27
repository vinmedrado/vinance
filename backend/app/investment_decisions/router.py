from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.investment_decisions.schemas import DecisionDetail, DecisionHistoryPage, DecisionMetrics
from backend.app.investment_decisions.service import (
    get_decision_metrics,
    get_owned_decision,
    list_decision_history,
    parse_decision_id,
)

router = APIRouter(prefix="/investments/decisions", tags=["investment-decisions"])


@router.get("/metrics", response_model=DecisionMetrics)
async def decision_metrics(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await get_decision_metrics(session, user_id=current_user.id)


@router.get("", response_model=DecisionHistoryPage)
async def decision_history(
    response: Response,
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=50),
    asset: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.\-]+$"),
    action: Literal["BUY", "WAIT", "AVOID", "NO_RECOMMENDATION"] | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "private, no-store"
    if (date_from and date_from.tzinfo is None) or (date_to and date_to.tzinfo is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Filtros de período devem incluir timezone")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="date_from deve ser anterior a date_to")
    return await list_decision_history(
        session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        asset=asset,
        recommendation=action,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
    )


@router.get("/{decision_id}", response_model=DecisionDetail)
async def decision_detail(
    decision_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "private, no-store"
    normalized_id = parse_decision_id(decision_id)
    if normalized_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisão não encontrada")
    decision = await get_owned_decision(session, user_id=current_user.id, decision_id=normalized_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisão não encontrada")
    return decision

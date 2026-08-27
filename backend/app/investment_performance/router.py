from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.investment_decisions.service import parse_decision_id
from backend.app.investment_performance.schemas import DecisionPerformanceDetail, PerformanceSummary
from backend.app.investment_performance.service import get_decision_performance, get_performance_summary


router = APIRouter(prefix="/investments", tags=["investment-performance"])


def _validate_period(date_from: datetime | None, date_to: datetime | None) -> None:
    if (date_from and date_from.tzinfo is None) or (date_to and date_to.tzinfo is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Filtros de período devem incluir timezone",
        )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from deve ser anterior a date_to",
        )


@router.get("/performance", response_model=PerformanceSummary)
async def performance_summary(
    response: Response,
    asset: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.\-]+$"),
    action: Literal["BUY", "WAIT", "AVOID"] | None = Query(default=None),
    horizon: Literal["1d", "7d", "30d"] | None = Query(default=None),
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] | None = Query(default=None),
    investor_profile: Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"] | None = Query(default=None),
    rule_version: str | None = Query(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._\-]+$"),
    recommendation_engine_version: str | None = Query(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9._\-]+$",
    ),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_period(date_from, date_to)
    response.headers["Cache-Control"] = "private, no-store"
    return await get_performance_summary(
        session,
        user_id=current_user.id,
        asset=asset,
        action=action,
        horizon=horizon,
        risk_level=risk_level,
        investor_profile=investor_profile,
        rule_version=rule_version,
        recommendation_engine_version=recommendation_engine_version,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/decisions/{decision_id}/performance", response_model=DecisionPerformanceDetail)
async def decision_performance(
    decision_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "private, no-store"
    normalized_id = parse_decision_id(decision_id)
    if normalized_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisão não encontrada")
    result = await get_decision_performance(
        session,
        user_id=current_user.id,
        decision_id=normalized_id,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisão não encontrada")
    return result

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.core.logging import get_logger
from backend.app.core.trace import decision_trace_context
from backend.app.intelligence import service
from backend.app.intelligence.schemas import AssetScoreRankingItem, BudgetAdvisorItem, DiversifiedBudgetAdvisorResponse, GuardrailItem, RecommendationResponse, TrendSignalItem
from backend.app.intelligence.services.asset_score_service import list_rankings
from backend.app.intelligence.services.budget_advisor_service import build_diversified_budget_advisor, build_explained_budget_recommendations, list_budget_recommendations
from backend.app.intelligence.services.recommendation_guardrail_service import list_guardrails
from backend.app.intelligence.services.trend_signal_service import list_trends
from backend.app.investment_decisions.service import (
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_SUCCESS,
    build_decision_audit,
    canonical_uuid,
    persist_decision_audit_fail_open,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
logger = get_logger(__name__)
MAX_BUDGET = Decimal("1000000000000")
MARKET_PATTERN = r"^[A-Za-z0-9_-]+$"
PROFILE_PATTERN = r"^[A-Za-z_-]+$"
TICKER_PATTERN = r"^[A-Za-z0-9.\-]+$"


@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    amount: Decimal | None = Query(default=None, ge=0, le=MAX_BUDGET),
    risk_profile: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.build_recommendation_base(
            session,
            user_id=current_user.id,
            amount=amount,
            risk_profile=risk_profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/rankings", response_model=list[AssetScoreRankingItem])
async def get_asset_rankings(
    market: str = Query(default="FII", min_length=1, max_length=32, pattern=MARKET_PATTERN),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await list_rankings(session, market=market, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/budget-advisor", response_model=None)
async def get_budget_advisor(
    response: Response,
    budget: Decimal = Query(..., gt=0, le=MAX_BUDGET),
    market: str = Query(default="FII", min_length=1, max_length=32, pattern=MARKET_PATTERN),
    limit: int = Query(default=20, ge=1, le=100),
    include_warnings: bool = Query(default=False),
    profile: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    trend_filter: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    explain: bool = Query(default=False),
    x_decision_id: str | None = Header(default=None, alias="X-Decision-ID"),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    decision_id = canonical_uuid(x_decision_id)
    correlation_id = canonical_uuid(x_correlation_id)
    generated_at = datetime.now(timezone.utc)
    started_at = perf_counter()
    trace_headers = {"X-Decision-ID": decision_id, "X-Correlation-ID": correlation_id}
    response.headers.update(trace_headers)
    response.headers["Cache-Control"] = "private, no-store"
    request_parameters = {
        "budget": budget,
        "market": market,
        "limit": limit,
        "include_warnings": include_warnings,
        "profile": profile,
        "trend_filter": trend_filter,
        "explain": explain,
    }

    with decision_trace_context(decision_id=decision_id, correlation_id=correlation_id, user_id=current_user.id):
        logger.info(
            "investment_decision.started",
            extra={"event": "investment_decision.started", "status": "STARTED"},
        )
        try:
            if explain:
                payload = await build_explained_budget_recommendations(
                    session,
                    budget=budget,
                    market=market,
                    limit=limit,
                    include_warnings=include_warnings,
                    profile=profile,
                    trend_filter=trend_filter,
                )
            else:
                payload = await list_budget_recommendations(
                    session,
                    budget=budget,
                    market=market,
                    limit=limit,
                    include_warnings=include_warnings,
                    profile=profile,
                    trend_filter=trend_filter,
                )
        except ValueError as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            record = build_decision_audit(
                decision_id=decision_id,
                correlation_id=correlation_id,
                user_id=current_user.id,
                request_parameters=request_parameters,
                payload={},
                latency_ms=latency_ms,
                status=STATUS_ERROR,
                error_code="INVALID_RECOMMENDATION_REQUEST",
                created_at=generated_at,
            )
            await persist_decision_audit_fail_open(session, record)
            logger.warning(
                "investment_decision.failed",
                extra={
                    "event": "investment_decision.failed",
                    "status": STATUS_ERROR,
                    "latency_ms": latency_ms,
                    "error_code": "INVALID_RECOMMENDATION_REQUEST",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                headers=trace_headers,
            ) from exc
        except Exception as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            record = build_decision_audit(
                decision_id=decision_id,
                correlation_id=correlation_id,
                user_id=current_user.id,
                request_parameters=request_parameters,
                payload={},
                latency_ms=latency_ms,
                status=STATUS_ERROR,
                error_code="RECOMMENDATION_ENGINE_ERROR",
                created_at=generated_at,
            )
            await persist_decision_audit_fail_open(session, record)
            logger.exception(
                "investment_decision.failed",
                extra={
                    "event": "investment_decision.failed",
                    "status": STATUS_ERROR,
                    "latency_ms": latency_ms,
                    "error_code": "RECOMMENDATION_ENGINE_ERROR",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Não foi possível gerar a recomendação.",
                headers=trace_headers,
            ) from exc

        latency_ms = round((perf_counter() - started_at) * 1000)
        has_recommendation = bool(payload.get("best_recommendation")) if isinstance(payload, dict) else bool(payload)
        record = build_decision_audit(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=current_user.id,
            request_parameters=request_parameters,
            payload=payload,
            latency_ms=latency_ms,
            status=STATUS_SUCCESS if has_recommendation else STATUS_EMPTY,
            created_at=generated_at,
        )
        audit_persisted = await persist_decision_audit_fail_open(session, record)
        if record.fallback_used:
            logger.warning(
                "investment_decision.fallback",
                extra={
                    "event": "investment_decision.fallback",
                    "asset": record.asset,
                    "status": record.status,
                    "latency_ms": latency_ms,
                    "fallback_used": True,
                },
            )
        logger.info(
            "investment_decision.completed",
            extra={
                "event": "investment_decision.completed",
                "asset": record.asset,
                "status": record.status,
                "latency_ms": latency_ms,
                "fallback_used": record.fallback_used,
                "audit_status": "PERSISTED" if audit_persisted else "FAILED",
            },
        )

        if isinstance(payload, dict):
            return {
                **payload,
                "decision_id": decision_id,
                "correlation_id": correlation_id,
                "generated_at": generated_at.isoformat(),
                "decision_action": record.recommendation,
                "audit_status": "PERSISTED" if audit_persisted else "FAILED",
            }
        return payload


@router.get("/recommendation/explain", response_model=None)
async def explain_recommendation(
    budget: Decimal = Query(..., gt=0, le=MAX_BUDGET),
    market: str = Query(default="FII", min_length=1, max_length=32, pattern=MARKET_PATTERN),
    profile: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    ticker: str | None = Query(default=None, min_length=1, max_length=32, pattern=TICKER_PATTERN),
    include_warnings: bool = Query(default=False),
    trend_filter: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = await build_explained_budget_recommendations(
            session,
            budget=budget,
            market=market,
            limit=100 if ticker else 20,
            include_warnings=include_warnings,
            profile=profile,
            trend_filter=trend_filter,
        )
        if ticker:
            normalized_ticker = ticker.upper()
            candidates = []
            if payload.get("best_recommendation"):
                candidates.append(payload["best_recommendation"])
            candidates.extend(payload.get("alternatives") or [])
            selected = next((item for item in candidates if str(item.get("ticker", "")).upper() == normalized_ticker), None)
            if selected is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ticker não encontrado nas recomendações disponíveis")
            payload["best_recommendation"] = selected
            payload["alternatives"] = [item for item in candidates if str(item.get("ticker", "")).upper() != normalized_ticker][:19]
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/budget-advisor/diversified", response_model=DiversifiedBudgetAdvisorResponse)
async def get_diversified_budget_advisor(
    budget: Decimal = Query(..., gt=0, le=MAX_BUDGET),
    profile: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    include_warnings: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await build_diversified_budget_advisor(session, budget=budget, profile=profile, include_warnings=include_warnings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/guardrails", response_model=list[GuardrailItem])
async def get_recommendation_guardrails(
    market: str = Query(default="FII", min_length=1, max_length=32, pattern=MARKET_PATTERN),
    guardrail_status: str | None = Query(default=None, alias="status", min_length=1, max_length=16, pattern=PROFILE_PATTERN),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await list_guardrails(session, market=market, status=guardrail_status, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/trends", response_model=list[TrendSignalItem])
async def get_trend_signals(
    market: str = Query(default="FII", min_length=1, max_length=32, pattern=MARKET_PATTERN),
    trend: str | None = Query(default=None, min_length=1, max_length=32, pattern=PROFILE_PATTERN),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await list_trends(session, market=market, trend=trend, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

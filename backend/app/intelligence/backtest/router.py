from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.intelligence.backtest.schemas import BacktestRunRequest, BacktestRunResponse, BacktestSummaryResponse
from backend.app.intelligence.backtest.service import get_backtest_summary, run_backtest_for_market

router = APIRouter(prefix="/backtest", tags=["intelligence-backtest"])


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(
    payload: BacktestRunRequest,
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - auth guard
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await run_backtest_for_market(
            session,
            market=payload.market,
            start_date=payload.start_date,
            end_date=payload.end_date,
            holding_period_days=payload.holding_period_days,
            top_n=payload.top_n,
            rebalance_frequency=payload.rebalance_frequency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "parameters": payload.model_dump(),
        "metrics": result["metrics"],
        "warnings": result["warnings"],
        "sample_size": result["sample_size"],
        "methodology": result["methodology"],
    }


@router.get("/summary", response_model=BacktestSummaryResponse)
async def summary(
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - auth guard
    session: AsyncSession = Depends(get_session),
):
    return await get_backtest_summary(session)

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from backend.app.quant_intelligence.schemas import BacktestRequest, InvestmentDecisionRequest, TrainModelRequest
from backend.app.quant_intelligence.service import (
    create_job,
    get_job,
    get_run_detail,
    history,
    investment_decision,
    market_universe,
    quant_operational_status,
    run_backtest,
    sync_market_snapshots,
    train_model,
)

router = APIRouter(prefix="/quant", tags=["Vinance Quant Intelligence"])


@router.get("/health")
def quant_health() -> dict:
    return quant_operational_status()


@router.get("/markets")
def markets(limit: int = Query(80, ge=1, le=300)) -> dict:
    return {"items": market_universe()[:limit]}


@router.post("/market-data/sync")
def sync_market_data() -> dict:
    return sync_market_snapshots(source="manual_api")


@router.post("/investment-decision")
def create_investment_decision(payload: InvestmentDecisionRequest) -> dict:
    return investment_decision(payload)


@router.post("/backtest/run")
def create_backtest(payload: BacktestRequest) -> dict:
    return run_backtest(payload)


@router.post("/backtest/async")
def create_backtest_async(payload: BacktestRequest) -> dict:
    job_id = f"quant-backtest-{uuid4().hex[:16]}"
    create_job(job_id, "quant_backtest", payload.model_dump())
    try:
        from workers.tasks import run_quant_backtest
        run_quant_backtest.delay(job_id, payload.model_dump())
        return {"job_id": job_id, "status": "queued", "mode": "celery"}
    except Exception as exc:
        result = run_backtest(payload)
        return {"job_id": job_id, "status": "completed_inline", "mode": "inline_fallback", "result": result, "warning": str(exc)}


@router.post("/ml/train")
def create_model_training(payload: TrainModelRequest) -> dict:
    return train_model(payload)


@router.post("/ml/train/async")
def create_model_training_async(payload: TrainModelRequest) -> dict:
    job_id = f"quant-train-{uuid4().hex[:16]}"
    create_job(job_id, "quant_training", payload.model_dump())
    try:
        from workers.tasks import run_quant_training
        run_quant_training.delay(job_id, payload.model_dump())
        return {"job_id": job_id, "status": "queued", "mode": "celery"}
    except Exception as exc:
        result = train_model(payload)
        return {"job_id": job_id, "status": "completed_inline", "mode": "inline_fallback", "result": result, "warning": str(exc)}


@router.get("/jobs/{job_id}")
def job_detail(job_id: str) -> dict:
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return row


@router.get("/runs/{kind}/{run_id}")
def run_detail(kind: str, run_id: int) -> dict:
    row = get_run_detail(kind, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return row


@router.get("/runs")
def runs(limit: int = Query(20, ge=1, le=100)) -> dict:
    return history(limit=limit)

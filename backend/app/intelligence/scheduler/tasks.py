from __future__ import annotations

from backend.app.core.celery import celery_app
from backend.app.core.celery_async import run_celery_coroutine
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.logging import get_logger
from backend.app.intelligence.feature_service import (
    compute_acoes_features,
    compute_all_features,
    compute_bdr_features,
    compute_cripto_features,
    compute_etf_features,
    compute_fii_features,
)

logger = get_logger(__name__)


async def _run_feature_job(fn, *, limit_assets: int | None = None) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            return await fn(session, limit_assets=limit_assets)
        except Exception as exc:  # noqa: BLE001 - scheduler must be resilient
            logger.exception("Intelligence feature task failed", extra={"task": fn.__name__, "error": str(exc)})
            return {"processed": 0, "inserted": 0, "updated": 0, "error": str(exc)}


@celery_app.task(name="intelligence.compute_daily_fii_features", queue="intelligence")
def compute_daily_fii_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_fii_features, limit_assets=limit_assets))


@celery_app.task(name="intelligence.compute_daily_acoes_features", queue="intelligence")
def compute_daily_acoes_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_acoes_features, limit_assets=limit_assets))


@celery_app.task(name="intelligence.compute_daily_etf_features", queue="intelligence")
def compute_daily_etf_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_etf_features, limit_assets=limit_assets))


@celery_app.task(name="intelligence.compute_daily_bdr_features", queue="intelligence")
def compute_daily_bdr_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_bdr_features, limit_assets=limit_assets))


@celery_app.task(name="intelligence.compute_daily_cripto_features", queue="intelligence")
def compute_daily_cripto_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_cripto_features, limit_assets=limit_assets))


@celery_app.task(name="intelligence.compute_all_market_features", queue="intelligence")
def compute_all_market_features(limit_assets: int | None = None) -> dict:
    return run_celery_coroutine(_run_feature_job(compute_all_features, limit_assets=limit_assets))


async def _run_ml_training_job(*, horizon_days: int = 90, min_samples: int = 30) -> dict:
    from backend.app.intelligence.ml.train import train_all_baselines

    async with AsyncSessionLocal() as session:
        try:
            return await train_all_baselines(session, horizon_days=horizon_days, min_samples=min_samples)
        except Exception as exc:  # noqa: BLE001 - scheduler must be resilient
            logger.exception("Intelligence ML baseline training task failed", extra={"error": str(exc)})
            return {"trained": 0, "error": str(exc)}


@celery_app.task(name="intelligence.train_ml_baselines_weekly", queue="intelligence")
def train_ml_baselines_weekly(horizon_days: int = 90, min_samples: int = 30) -> dict:
    # Fase 20 creates the task but intentionally does not enable beat by default.
    # Operators can run it manually after confirming enough historical data.
    return run_celery_coroutine(_run_ml_training_job(horizon_days=horizon_days, min_samples=min_samples))

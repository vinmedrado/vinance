from __future__ import annotations

import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import after_setup_logger, after_setup_task_logger
from kombu import Queue

from backend.app.core.config import settings
from backend.app.core.logging import StructuredFormatter


# FASE 29: reduce third-party HTTP client noise in Celery workers/beat.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _configure_structured_celery_logging(logger: logging.Logger, *args, **kwargs) -> None:
    """Keep worker/beat output traceable with the same redaction as the API."""

    formatter = StructuredFormatter()
    for handler in logger.handlers:
        handler.setFormatter(formatter)


after_setup_logger.connect(_configure_structured_celery_logging, weak=False)
after_setup_task_logger.connect(_configure_structured_celery_logging, weak=False)

celery_app = Celery(
    "vinance_v2",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_result_backend,
    include=[
        "backend.app.market.scheduler.tasks",
        "backend.app.market.tasks",
        "backend.app.intelligence.scheduler.tasks",
        "backend.app.investment_performance.tasks",
        "backend.app.investment_alerts.tasks",
    ],
)

celery_app.conf.update(
    timezone=settings.celery_timezone,
    enable_utc=False,
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("market"),
        Queue("intelligence"),
    ),
    task_routes={
        "market.sync_macro_indicators": {"queue": "market"},
        "market.sync_tesouro_direto": {"queue": "market"},
        "market.sync_historical_prices_weekly": {"queue": "market"},
        "market.cleanup_old_asset_prices": {"queue": "market"},
        "market.sync_cripto_coingecko": {"queue": "market"},
        "market.sync_fiis": {"queue": "market"},
        "market.sync_acoes": {"queue": "market"},
        "market.sync_etfs": {"queue": "market"},
        "market.sync_bdrs": {"queue": "market"},
        "market.sync_fiis_investidor10": {"queue": "market"},
        "market.sync_acoes_investidor10": {"queue": "market"},
        "market.sync_etfs_investidor10": {"queue": "market"},
        "market.sync_bdrs_investidor10": {"queue": "market"},
        "market.sync_all_investidor10": {"queue": "market"},
        "market.calculate_asset_scores": {"queue": "intelligence"},
        "market.calculate_recommendation_guardrails": {"queue": "intelligence"},
        "market.calculate_trend_signals": {"queue": "intelligence"},
        "intelligence.compute_daily_fii_features": {"queue": "intelligence"},
        "intelligence.compute_daily_acoes_features": {"queue": "intelligence"},
        "intelligence.compute_daily_etf_features": {"queue": "intelligence"},
        "intelligence.compute_daily_bdr_features": {"queue": "intelligence"},
        "intelligence.compute_daily_cripto_features": {"queue": "intelligence"},
        "intelligence.compute_all_market_features": {"queue": "intelligence"},
        "intelligence.train_ml_baselines_weekly": {"queue": "intelligence"},
        "investment_performance.evaluate_due": {"queue": "intelligence"},
        "investment_alerts.evaluate_subscriptions": {"queue": "intelligence"},
    },
    beat_schedule={
        "market-sync-macro-daily": {
            "task": "market.sync_macro_indicators",
            "schedule": crontab(hour=20, minute=0),
        },
        "market-sync-tesouro-daily": {
            "task": "market.sync_tesouro_direto",
            "schedule": crontab(hour=20, minute=15),
        },
        "market-sync-historical-prices-weekly-sunday": {
            "task": "market.sync_historical_prices_weekly",
            "schedule": crontab(hour=3, minute=0, day_of_week="sun"),
        },
        "market-cleanup-old-prices-daily": {
            "task": "market.cleanup_old_asset_prices",
            "schedule": crontab(hour=4, minute=0),
        },
        "market-sync-cripto-coingecko-every-10-min": {
            "task": "market.sync_cripto_coingecko",
            "schedule": crontab(minute="*/10"),
        },
        "market-sync-investidor10-daily-after-close": {
            "task": "market.sync_all_investidor10",
            "schedule": crontab(hour=21, minute=0),
        },
        "market-calculate-asset-scores-daily-after-investidor10": {
            "task": "market.calculate_asset_scores",
            "schedule": crontab(hour=21, minute=35),
            "options": {"queue": "intelligence"},
        },
        "market-calculate-recommendation-guardrails-daily-after-scores": {
            "task": "market.calculate_recommendation_guardrails",
            "schedule": crontab(hour=21, minute=45),
            "options": {"queue": "intelligence"},
        },
        "market-calculate-trend-signals-daily-after-guardrails": {
            "task": "market.calculate_trend_signals",
            "schedule": crontab(hour=21, minute=55),
            "options": {"queue": "intelligence"},
        },
        "investment-performance-evaluate-daily": {
            "task": "investment_performance.evaluate_due",
            "schedule": crontab(hour=5, minute=30),
            "options": {"queue": "intelligence"},
        },
        "investment-alerts-evaluate-daily-after-intelligence": {
            "task": "investment_alerts.evaluate_subscriptions",
            "schedule": crontab(hour=22, minute=10),
            "options": {"queue": "intelligence"},
        },
        "intelligence-compute-all-market-features-daily": {
            "task": "intelligence.compute_all_market_features",
            "schedule": crontab(hour=23, minute=30),
            "options": {"queue": "intelligence"},
        },
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # FASE 29: reduce Celery runtime noise without hiding task errors.
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

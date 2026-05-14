
from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

broker = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/0"))
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

app = Celery("financeos", broker=broker, backend=backend)
app.conf.timezone = "UTC"
app.conf.beat_schedule = {
    "sync-prices-daily": {"task": "workers.tasks.sync_all_prices", "schedule": crontab(hour=6, minute=0)},
    "run-predictions-daily": {"task": "workers.tasks.run_ml_predictions", "schedule": crontab(hour=7, minute=0)},
    "drift-check-weekly": {"task": "workers.tasks.check_drift", "schedule": crontab(day_of_week=1, hour=8, minute=0)},
}

from backend.app.core.celery import celery_app

app = celery_app

__all__ = ["app", "celery_app"]

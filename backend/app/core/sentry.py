from __future__ import annotations

import logging

from backend.app.core.settings import get_settings

logger = logging.getLogger("financeos.api")


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn_backend:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            release=f"financeos@{settings.app_version}",
            traces_sample_rate=float(__import__("os").getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )
        logger.info("sentry_backend_enabled")
    except Exception as exc:  # optional dependency / safe fallback
        logger.warning("sentry_backend_disabled", extra={"reason": str(exc)})

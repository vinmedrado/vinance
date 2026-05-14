from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database import init_db
from backend.app.core.routers import core
from backend.app.financing.routers import financing
from backend.app.financial.routers import financial
from backend.app.market.routers import market, investments
from backend.app.investment.routers import investment
from backend.app.api_operational.router import router as operational_api_router
from backend.app.erp.router import router as erp_router

from backend.app.api_operational.db import connect as operational_db_connect
from backend.app.api_operational.indexes import ensure_indexes
from backend.app.core.hardening import install_hardening
from backend.app.core.observability import configure_logging
from backend.app.core.settings import get_settings
from backend.app.core.sentry import init_sentry
from backend.app.analytics.router import router as analytics_router
from backend.app.demo.router import router as demo_router
from backend.app.enterprise.router import router as enterprise_router
from backend.app.intelligence.router import router as intelligence_router

settings = get_settings()
settings.validate_for_runtime()
configure_logging()
init_sentry()

app = FastAPI(
    title="FinanceOS Unified API",
    version=settings.app_version,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)
install_hardening(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    try:
        with operational_db_connect() as conn:
            ensure_indexes(conn)
    except Exception:
        pass

@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment, "version": app.version}

@app.get("/ready")
def ready():
    return {"status": "ready", "checks": {"api": "ok"}, "environment": settings.environment}

@app.get("/live")
def live():
    return {"status": "live", "service": settings.app_name}

@app.get("/metrics")
def metrics():
    return {"service": settings.app_name, "environment": settings.environment, "status": "ok"}

app.include_router(core.router)
app.include_router(financing.router)
app.include_router(financial.router)
app.include_router(market.router)
app.include_router(investments.router)
app.include_router(investment.router)

# PATCH 11 - Operational API
app.include_router(operational_api_router)

try:
    from backend.app.auth.router import router as auth_router
except ModuleNotFoundError:
    from backend.app.auth import router as auth_router
app.include_router(auth_router)
app.include_router(auth_router, prefix="/api")
app.include_router(erp_router)
app.include_router(analytics_router)
app.include_router(analytics_router, prefix="/api")
app.include_router(demo_router)
app.include_router(demo_router, prefix="/api")
app.include_router(enterprise_router)
app.include_router(intelligence_router)

from backend.app.billing.stripe_router import router as billing_router
app.include_router(billing_router)
app.include_router(billing_router, prefix="/api")


from services.production_health_service import run_full_healthcheck

@app.get("/health/full")
def health_full():
    return run_full_healthcheck()

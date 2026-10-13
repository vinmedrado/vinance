from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.router import api_router
from backend.app.intelligence.router import router as intelligence_router
from backend.app.core.config import settings
from backend.app.core.database import close_database, validate_database_connection
from backend.app.core.errors import register_exception_handlers
from backend.app.core.hardening import install_hardening
from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.readiness import schema_revision_status
from backend.app.core.redis import close_redis, validate_redis_connection

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s %s", settings.app_name, settings.app_version)
    yield
    logger.info("Shutting down %s", settings.app_name)
    await close_redis()
    await close_database()


docs_enabled = settings.effective_api_docs_enabled
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
register_exception_handlers(app)
install_hardening(app)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Decision-ID", "X-Correlation-ID"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness only: dependencies belong to /ready."""

    return {
        "status": "healthy",
        "api": "ok",
        "version": settings.app_version,
        "commit": (settings.app_commit_sha or os.getenv("APP_COMMIT_SHA", "unknown"))[:40],
    }


@app.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    database_ok = await validate_database_connection()
    redis_ok = await validate_redis_connection()
    revision = await schema_revision_status() if database_ok else None
    schema_ok = bool(revision and revision.compatible)
    status = "ready" if database_ok and redis_ok and schema_ok else "not_ready"
    if status != "ready":
        response.status_code = 503
    return {
        "status": status,
        "api": "ok",
        "database": "ok" if database_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "schema": "ok" if schema_ok else "error",
    }


app.include_router(api_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api")

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.auth.router import router as auth_router
from backend.app.intelligence.router import router as intelligence_router
from backend.app.core.config import settings
from backend.app.core.database import close_database, validate_database_connection
from backend.app.core.errors import register_exception_handlers
from backend.app.core.logging import configure_logging, get_logger
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


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Decision-ID", "X-Correlation-ID"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if (
        request.url.path.startswith("/api/v1/financial/households/")
        and "/action-plan" in request.url.path
    ):
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/health")
async def health(response: Response) -> dict[str, str]:
    database_ok = await validate_database_connection()
    redis_ok = await validate_redis_connection()
    status = "healthy" if database_ok and redis_ok else "unhealthy"
    if status == "unhealthy":
        response.status_code = 503
    return {
        "status": status,
        "api": "ok",
        "database": "ok" if database_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }


app.include_router(api_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api")
app.include_router(auth_router)

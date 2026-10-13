from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


def error_response(status_code: int, error: str, details=None, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"success": False, "error": error, "details": details},
            custom_encoder={Exception: str},
        ),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    def correlation_headers(request: Request) -> dict[str, str]:
        correlation_id = getattr(request.state, "correlation_id", None)
        return {"X-Correlation-ID": str(correlation_id)} if correlation_id else {}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        headers = {**correlation_headers(request), **(exc.headers or {})}
        return error_response(exc.status_code, str(exc.detail), None, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "Validation error", exc.errors(), headers=correlation_headers(request))

    @app.exception_handler(Exception)
    async def internal_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "Internal server error", None, headers=correlation_headers(request))

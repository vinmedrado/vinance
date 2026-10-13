
from __future__ import annotations

import os
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _correlation_id(request: Request) -> str:
    candidate = request.headers.get("X-Correlation-ID", "").strip()
    try:
        return str(UUID(candidate))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


def install_hardening(app: FastAPI) -> None:
    max_payload_bytes = int(os.getenv("MAX_PAYLOAD_BYTES", "1048576"))

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        correlation_id = _correlation_id(request)
        request.state.correlation_id = correlation_id
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_payload_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"success": False, "error": "Payload muito grande", "details": None},
                        headers={"X-Correlation-ID": correlation_id, "Cache-Control": "private, no-store"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Content-Length inválido", "details": None},
                    headers={"X-Correlation-ID": correlation_id, "Cache-Control": "private, no-store"},
                )

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response

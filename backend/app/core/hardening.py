
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("financeos.api")
START_TIME = time.time()
_hits: dict[str, Deque[float]] = defaultdict(deque)

def get_uptime_seconds() -> int:
    return int(time.time() - START_TIME)

def install_hardening(app: FastAPI) -> None:
    rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes"}
    max_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "180"))
    window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        request_id = f"{int(time.time() * 1000)}"
        client = request.client.host if request.client else "unknown"
        request.state.request_id = request_id
        if int(request.headers.get("content-length", "0") or 0) > int(os.getenv("MAX_PAYLOAD_BYTES", "1048576")):
            return JSONResponse(status_code=413, content={"detail": "Payload muito grande."})
        if rate_limit_enabled:
            now = time.time()
            bucket = _hits[client]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return JSONResponse(status_code=429, content={"detail": "Rate limit excedido. Tente novamente em instantes."})
            bucket.append(now)
        try:
            response = await call_next(request)
            response.headers["X-FinanceOS-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            return response
        except Exception as exc:  # noqa: BLE001 - global API safety net
            logger.exception("unhandled_api_error", extra={"path": str(request.url.path), "client": client})
            return JSONResponse(status_code=500, content={"detail": "Erro interno controlado. Consulte os logs do servidor."})

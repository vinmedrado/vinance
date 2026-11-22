from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from backend.app.core.config import settings


def validate_cookie_origin(request: Request) -> None:
    """Protect state-changing cookie/session endpoints against cross-site requests."""

    if not settings.is_production:
        return
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = {item.rstrip("/") for item in settings.cors_origin_list}
    if not origin or origin.rstrip("/") not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")

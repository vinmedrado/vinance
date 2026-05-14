from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone


def sha256_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_secure_token_urlsafe() -> str:
    return secrets.token_urlsafe(48)


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def expires_in(**kwargs) -> datetime:
    return utcnow() + timedelta(**kwargs)

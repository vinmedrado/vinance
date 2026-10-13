from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: str
    session_id: str | None
    token_id: str | None


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    *,
    session_id: str | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),
        "type": "access",
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    claims = decode_access_token_claims(token)
    return claims.subject if claims else None


def decode_access_token_claims(token: str) -> AccessTokenClaims | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not isinstance(subject, str) or payload.get("type", "access") != "access":
            return None
        session_id = payload.get("sid")
        token_id = payload.get("jti")
        return AccessTokenClaims(
            subject=subject,
            session_id=session_id if isinstance(session_id, str) else None,
            token_id=token_id if isinstance(token_id, str) else None,
        )
    except JWTError:
        return None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

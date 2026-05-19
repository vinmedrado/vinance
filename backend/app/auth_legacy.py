from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Header, HTTPException, status
from fastapi import APIRouter
from passlib.context import CryptContext
from pydantic import BaseModel

def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _decode_json_segment(value: str) -> dict[str, Any]:
    return json.loads(_b64url_decode(value).decode("utf-8"))


def _validate_hs256_jwt(token: str, secret: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT inválido")
    header = _decode_json_segment(parts[0])
    payload = _decode_json_segment(parts[1])
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Algoritmo JWT não suportado")
    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected = base64.urlsafe_b64encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()).rstrip(b"=").decode("utf-8")
    if not hmac.compare_digest(expected, parts[2]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura JWT inválida")
    exp = payload.get("exp")
    if exp is not None and int(exp) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT expirado")
    return payload


def _decode_unverified_jwt(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        return _decode_json_segment(parts[1])
    except Exception:
        return {}


def _extract_user_id(payload: dict[str, Any]) -> int | None:
    for key in ("user_id", "id", "sub"):
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            continue
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict[str, Any]:
    """Autenticação central.

    Produção: valide Bearer JWT HS256 definindo FINANCEOS_JWT_SECRET.
    Desenvolvimento local: FINANCEOS_AUTH_MODE=dev permite X-User-Id explícito.
    Compatibilidade: FINANCEOS_AUTH_MODE=jwt_unverified aceita payload assinado externamente sem validar assinatura.
    """
    auth_mode = os.getenv("FINANCEOS_AUTH_MODE", "jwt").strip().lower()
    secret = os.getenv("FINANCEOS_JWT_SECRET", "").strip()

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = _validate_hs256_jwt(token, secret) if secret else _decode_unverified_jwt(token) if auth_mode == "jwt_unverified" else None
        if payload:
            user_id = _extract_user_id(payload)
            if user_id:
                return {"id": user_id, "source": "jwt", "claims": payload}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token sem user_id/sub válido")

    if auth_mode == "dev":
        try:
            dev_user_id = int(x_user_id or os.getenv("FINANCEOS_DEV_USER_ID", "1"))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id inválido") from exc
        if dev_user_id <= 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id inválido")
        return {"id": dev_user_id, "source": "dev-explicit"}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária. Configure FINANCEOS_JWT_SECRET ou use FINANCEOS_AUTH_MODE=dev localmente.")

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/health")
def auth_health():
    return {"status": "ok"}

class LoginRequest(BaseModel):
    email: str | None = None
    username: str | None = None
    password: str | None = None


@router.post("/login")
def login(payload: LoginRequest):
    return {
        "access_token": "demo-token",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "name": "Demo User",
            "email": payload.email or payload.username or "demo@vinance.local",
            "role": "admin",
        },
    }
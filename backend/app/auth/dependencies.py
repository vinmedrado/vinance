from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_sync_session
from backend.app.auth.jwt_handler import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_sync_session)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    try:
        import os, redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        if r.exists(f"blacklist:{token[:32]}"):
            raise HTTPException(status_code=401, detail="Token revogado")
    except HTTPException:
        raise
    except Exception:
        pass
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem usuário")
    row = db.execute(text("""
        SELECT u.id, u.email, u.full_name, u.is_active, u.email_verified_at,
               om.organization_id, om.role, COALESCE(o.plan, s.plan, 'free') AS plan
        FROM users u
        LEFT JOIN organization_members om ON om.user_id = u.id AND om.is_active = true
        LEFT JOIN organizations o ON o.id = om.organization_id
        LEFT JOIN subscriptions s ON s.organization_id = o.id
        WHERE u.id = :id AND u.is_active = true
        ORDER BY CASE om.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, om.id ASC
        LIMIT 1
    """), {"id": str(user_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    data = dict(row)
    data["claims"] = payload
    return data

def require_role(roles: list[str]):
    def checker(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return user
    return checker

def require_plan(plans: list[str]):
    def checker(user=Depends(get_current_user)):
        if user.get("plan") not in plans:
            raise HTTPException(status_code=403, detail="Plano insuficiente")
        return user
    return checker

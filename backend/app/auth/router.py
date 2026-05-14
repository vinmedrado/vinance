from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_sync_session
from backend.app.auth.password import hash_password, verify_password
from backend.app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from backend.app.auth.dependencies import oauth2_scheme, get_current_user
from backend.app.enterprise.security import expires_in, new_id, sha256_token
from backend.app.enterprise.audit import record_event
from backend.app.enterprise.rbac import ROLE_PERMISSIONS

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    tenant_name: str | None = None
    organization_name: str | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class RefreshIn(BaseModel):
    refresh_token: str

class PasswordResetRequestIn(BaseModel):
    email: EmailStr

class PasswordResetCompleteIn(BaseModel):
    token: str
    new_password: str

def _slug(value: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or new_id()[:8]

def _issue_tokens(db: Session, *, user_id: str, organization_id: str, role: str, plan: str, request: Request | None = None) -> dict:
    access_payload = {"sub": user_id, "organization_id": organization_id, "role": role, "plan": plan}
    refresh_payload = {**access_payload, "token_family": new_id()}
    access = create_access_token(access_payload)
    refresh = create_refresh_token(refresh_payload)
    session_id = new_id()
    db.execute(text("""
        INSERT INTO user_sessions (id, organization_id, user_id, refresh_token_hash, ip_address, user_agent, expires_at)
        VALUES (:id, :organization_id, :user_id, :refresh_token_hash, :ip, :ua, :expires_at)
    """), {"id": session_id, "organization_id": organization_id, "user_id": user_id, "refresh_token_hash": sha256_token(refresh), "ip": request.client.host if request and request.client else None, "ua": request.headers.get("user-agent") if request else None, "expires_at": expires_in(days=14)})
    db.execute(text("""
        INSERT INTO refresh_tokens (id, organization_id, user_id, session_id, token_hash, expires_at)
        VALUES (:id, :organization_id, :user_id, :session_id, :token_hash, :expires_at)
    """), {"id": new_id(), "organization_id": organization_id, "user_id": user_id, "session_id": session_id, "token_hash": sha256_token(refresh), "expires_at": expires_in(days=14)})
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@router.post("/register")
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_sync_session)):
    exists = db.execute(text("SELECT id FROM users WHERE email=:email"), {"email": payload.email}).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    org_name = payload.organization_name or payload.tenant_name or (payload.full_name or payload.email).split("@")[0]
    base_slug = _slug(org_name)
    slug = base_slug
    i = 2
    while db.execute(text("SELECT id FROM organizations WHERE slug=:slug"), {"slug": slug}).first():
        slug = f"{base_slug}-{i}"; i += 1
    organization_id = new_id()
    user_id = new_id()
    db.execute(text("""
        INSERT INTO organizations (id, name, slug, plan, subscription_status, is_active)
        VALUES (:id, :name, :slug, 'free', 'trialing', true)
    """), {"id": organization_id, "name": org_name, "slug": slug})
    db.execute(text("""
        INSERT INTO users (id, email, hashed_password, full_name, is_active)
        VALUES (:id, :email, :hashed_password, :full_name, true)
    """), {"id": user_id, "email": payload.email, "hashed_password": hash_password(payload.password), "full_name": payload.full_name})
    db.execute(text("INSERT INTO organization_members (organization_id, user_id, role, is_active) VALUES (:organization_id, :user_id, 'owner', true)"), {"organization_id": organization_id, "user_id": user_id})
    db.execute(text("INSERT INTO subscriptions (organization_id, plan, status) VALUES (:organization_id, 'free', 'trialing')"), {"organization_id": organization_id})
    for role, perms in ROLE_PERMISSIONS.items():
        db.execute(text("INSERT INTO roles (name, description) VALUES (:name, :desc) ON CONFLICT (name) DO NOTHING"), {"name": role, "desc": f"Default {role} role"})
        for perm in perms:
            if perm == "*":
                continue
            db.execute(text("INSERT INTO permissions (name, description) VALUES (:name, :desc) ON CONFLICT (name) DO NOTHING"), {"name": perm, "desc": perm})
            db.execute(text("INSERT INTO role_permissions (role_name, permission_name) VALUES (:role, :perm) ON CONFLICT (role_name, permission_name) DO NOTHING"), {"role": role, "perm": perm})
    tokens = _issue_tokens(db, user_id=user_id, organization_id=organization_id, role="owner", plan="free", request=request)
    record_event(db, organization_id=organization_id, user_id=user_id, action="auth.login", entity_type="user", entity_id=user_id, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {**tokens, "user": {"id": user_id, "email": payload.email, "organization_id": organization_id, "role": "owner", "plan": "free"}}

@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_sync_session)):
    user = db.execute(text("SELECT * FROM users WHERE email=:email AND is_active=true"), {"email": payload.email}).mappings().first()
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    member = db.execute(text("""
        SELECT om.organization_id, om.role, COALESCE(o.plan, s.plan, 'free') AS plan
        FROM organization_members om JOIN organizations o ON o.id=om.organization_id
        LEFT JOIN subscriptions s ON s.organization_id=o.id
        WHERE om.user_id=:user_id AND om.is_active=true AND o.is_active=true
        ORDER BY CASE om.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, om.id ASC LIMIT 1
    """), {"user_id": str(user["id"])}).mappings().first()
    if not member:
        raise HTTPException(status_code=403, detail="Usuário sem organização ativa")
    db.execute(text("UPDATE users SET last_login_at=:now WHERE id=:id"), {"now": datetime.now(timezone.utc), "id": str(user["id"])})
    tokens = _issue_tokens(db, user_id=str(user["id"]), organization_id=str(member["organization_id"]), role=str(member["role"]), plan=str(member["plan"]), request=request)
    record_event(db, organization_id=str(member["organization_id"]), user_id=str(user["id"]), action="auth.login", entity_type="user", entity_id=str(user["id"]), ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {**tokens, "user": {"id": str(user["id"]), "email": user["email"], "organization_id": str(member["organization_id"]), "role": member["role"], "plan": member["plan"]}}

@router.post("/refresh")
def refresh(payload: RefreshIn, request: Request, db: Session = Depends(get_sync_session)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    old_hash = sha256_token(payload.refresh_token)
    stored = db.execute(text("SELECT * FROM refresh_tokens WHERE token_hash=:hash AND revoked_at IS NULL AND expires_at > NOW()"), {"hash": old_hash}).mappings().first()
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token expirado ou revogado")
    user = db.execute(text("SELECT id, email, is_active FROM users WHERE id=:id AND is_active=true"), {"id": data["sub"]}).mappings().first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    member = db.execute(text("SELECT om.organization_id, om.role, COALESCE(o.plan, s.plan, 'free') AS plan FROM organization_members om JOIN organizations o ON o.id=om.organization_id LEFT JOIN subscriptions s ON s.organization_id=o.id WHERE om.user_id=:user_id AND om.organization_id=:org_id AND om.is_active=true LIMIT 1"), {"user_id": str(user["id"]), "org_id": str(stored["organization_id"])}).mappings().first()
    if not member:
        raise HTTPException(status_code=403, detail="Organização inválida")
    access = create_access_token({"sub": str(user["id"]), "organization_id": str(member["organization_id"]), "role": member["role"], "plan": member["plan"]})
    new_refresh = create_refresh_token({"sub": str(user["id"]), "organization_id": str(member["organization_id"]), "role": member["role"], "plan": member["plan"], "token_family": data.get("token_family") or new_id()})
    new_hash = sha256_token(new_refresh)
    session_id = new_id()
    db.execute(text("UPDATE refresh_tokens SET revoked_at=NOW(), replaced_by_hash=:new_hash WHERE token_hash=:old_hash"), {"old_hash": old_hash, "new_hash": new_hash})
    db.execute(text("UPDATE user_sessions SET revoked_at=NOW() WHERE refresh_token_hash=:old_hash"), {"old_hash": old_hash})
    db.execute(text("INSERT INTO user_sessions (id, organization_id, user_id, refresh_token_hash, ip_address, user_agent, expires_at) VALUES (:id, :organization_id, :user_id, :refresh_token_hash, :ip, :ua, :expires_at)"), {"id": session_id, "organization_id": str(member["organization_id"]), "user_id": str(user["id"]), "refresh_token_hash": new_hash, "ip": request.client.host if request.client else None, "ua": request.headers.get("user-agent"), "expires_at": expires_in(days=14)})
    db.execute(text("INSERT INTO refresh_tokens (id, organization_id, user_id, session_id, token_hash, expires_at) VALUES (:id, :organization_id, :user_id, :session_id, :token_hash, :expires_at)"), {"id": new_id(), "organization_id": str(member["organization_id"]), "user_id": str(user["id"]), "session_id": session_id, "token_hash": new_hash, "expires_at": expires_in(days=14)})
    record_event(db, organization_id=str(member["organization_id"]), user_id=str(user["id"]), action="auth.refresh", entity_type="user", entity_id=str(user["id"]), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}

@router.post("/logout")
def logout(request: Request, token: str | None = Depends(oauth2_scheme), current_user: dict = Depends(get_current_user), db: Session = Depends(get_sync_session)):
    if token:
        token_hash = sha256_token(token)
        db.execute(text("UPDATE refresh_tokens SET revoked_at=NOW() WHERE user_id=:user_id AND revoked_at IS NULL"), {"user_id": current_user["id"]})
        db.execute(text("UPDATE user_sessions SET revoked_at=NOW() WHERE user_id=:user_id AND revoked_at IS NULL"), {"user_id": current_user["id"]})
        try:
            import os, time, redis
            r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            data = decode_token(token); ttl = max(0, int(data.get("exp", 0) - time.time()))
            if ttl > 0: r.setex(f"blacklist:{token[:32]}", ttl, "1")
        except Exception:
            pass
    record_event(db, organization_id=str(current_user["organization_id"]), user_id=str(current_user["id"]), action="auth.logout", entity_type="user", entity_id=str(current_user["id"]), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {"ok": True}

@router.post("/password-reset/request")
def password_reset_request(payload: PasswordResetRequestIn, request: Request, db: Session = Depends(get_sync_session)):
    user = db.execute(text("SELECT id FROM users WHERE email=:email"), {"email": payload.email}).mappings().first()
    if user:
        raw_token = new_id() + new_id()
        db.execute(text("INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at) VALUES (:id, :user_id, :token_hash, :expires_at)"), {"id": new_id(), "user_id": str(user["id"]), "token_hash": sha256_token(raw_token), "expires_at": expires_in(hours=1)})
        org = db.execute(text("SELECT organization_id FROM organization_members WHERE user_id=:id LIMIT 1"), {"id": str(user["id"])}).scalar()
        if org:
            record_event(db, organization_id=str(org), user_id=str(user["id"]), action="auth.password_reset_requested", entity_type="user", entity_id=str(user["id"]), request_id=getattr(request.state, "request_id", None))
        db.commit()
    return {"ok": True, "message": "Se o email existir, enviaremos as instruções."}

@router.post("/password-reset/complete")
def password_reset_complete(payload: PasswordResetCompleteIn, request: Request, db: Session = Depends(get_sync_session)):
    row = db.execute(text("SELECT * FROM password_reset_tokens WHERE token_hash=:hash AND used_at IS NULL AND expires_at > NOW()"), {"hash": sha256_token(payload.token)}).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")
    db.execute(text("UPDATE users SET hashed_password=:password WHERE id=:id"), {"password": hash_password(payload.new_password), "id": row["user_id"]})
    db.execute(text("UPDATE password_reset_tokens SET used_at=NOW() WHERE id=:id"), {"id": row["id"]})
    org = db.execute(text("SELECT organization_id FROM organization_members WHERE user_id=:id LIMIT 1"), {"id": str(row["user_id"])}).scalar()
    if org:
        record_event(db, organization_id=str(org), user_id=str(row["user_id"]), action="auth.password_reset_completed", entity_type="user", entity_id=str(row["user_id"]), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {"ok": True}

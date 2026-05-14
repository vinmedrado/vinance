from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_sync_session
try:
    from backend.app.auth.dependencies import get_current_user
except ModuleNotFoundError:
    from backend.app.auth import get_current_user
from backend.app.enterprise.rbac import has_permission

@dataclass(frozen=True)
class OrganizationContext:
    user_id: str
    organization_id: str
    role: str
    permissions: set[str]
    plan: str = "free"
    raw: dict[str, Any] | None = None

TenantContext = OrganizationContext

def _first(value: Any, *keys: str) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if value.get(key) not in (None, ""):
                return value.get(key)
    return None

def get_organization_context(request: Request, current_user: dict[str, Any] = Depends(get_current_user), db: Session = Depends(get_sync_session)) -> OrganizationContext:
    claims = current_user.get("claims") if isinstance(current_user.get("claims"), dict) else current_user
    user_id = str(_first(current_user, "id", "user_id", "sub") or _first(claims, "sub", "user_id", "id") or "")
    org_id = str(_first(current_user, "organization_id") or _first(claims, "organization_id") or "")
    role = str(_first(current_user, "role") or _first(claims, "role") or "viewer")
    plan = str(_first(current_user, "plan") or _first(claims, "plan") or "free")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem usuário válido")
    row = None
    if org_id:
        row = db.execute(text("""
            SELECT om.organization_id, om.role, COALESCE(o.plan, s.plan, :plan) AS plan
            FROM organization_members om
            JOIN organizations o ON o.id = om.organization_id
            LEFT JOIN subscriptions s ON s.organization_id = o.id
            WHERE om.user_id = :user_id AND om.organization_id = :org_id AND om.is_active = true AND o.is_active = true
            LIMIT 1
        """), {"user_id": user_id, "org_id": org_id, "plan": plan}).mappings().first()
    if not row:
        row = db.execute(text("""
            SELECT om.organization_id, om.role, COALESCE(o.plan, s.plan, :plan) AS plan
            FROM organization_members om
            JOIN organizations o ON o.id = om.organization_id
            LEFT JOIN subscriptions s ON s.organization_id = o.id
            WHERE om.user_id = :user_id AND om.is_active = true AND o.is_active = true
            ORDER BY CASE om.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, om.id ASC
            LIMIT 1
        """), {"user_id": user_id, "plan": plan}).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem organização ativa")
    org_id, role, plan = str(row["organization_id"]), str(row["role"]), str(row["plan"] or plan)
    perms = {r["permission_name"] for r in db.execute(text("SELECT permission_name FROM role_permissions WHERE role_name=:role"), {"role": role}).mappings().all()}
    request.state.user_id = user_id
    request.state.organization_id = org_id
    request.state.role = role
    return OrganizationContext(user_id=user_id, organization_id=org_id, role=role, permissions=perms, plan=plan, raw=current_user)

def get_current_organization(ctx: OrganizationContext = Depends(get_organization_context)) -> str:
    return ctx.organization_id

def get_tenant_context(request: Request, current_user: dict[str, Any] = Depends(get_current_user), db: Session = Depends(get_sync_session)) -> OrganizationContext:
    return get_organization_context(request, current_user, db)

def require_permission(permission_name: str):
    def checker(ctx: OrganizationContext = Depends(get_organization_context)) -> OrganizationContext:
        if permission_name not in ctx.permissions and not has_permission(ctx.role, permission_name):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
        return ctx
    return checker

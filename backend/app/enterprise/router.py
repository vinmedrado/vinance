from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_sync_session
from backend.app.enterprise.context import TenantContext, get_tenant_context, require_permission
from backend.app.services.plan_limits_service import PLAN_LIMITS, PlanLimitExceeded, ensure_feature_allowed
try:
    from backend.app.auth.password import hash_password
except ModuleNotFoundError:
    from backend.app.auth import hash_password
from backend.app.enterprise.security import new_id
from backend.app.enterprise.audit import record_event

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


@router.get("/me")
def enterprise_me(ctx: TenantContext = Depends(get_tenant_context)):
    return {"user_id": ctx.user_id, "organization_id": ctx.organization_id, "role": ctx.role, "plan": ctx.plan}


@router.get("/audit-logs")
def list_audit_logs(
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_sync_session),
    ctx: TenantContext = Depends(require_permission("audit.view")),
):
    sql = """
        SELECT id, organization_id, user_id, action, entity_type, entity_id, before_json, after_json, ip_address, user_agent, request_id, created_at
        FROM audit_logs
        WHERE organization_id = :organization_id
    """
    params = {"organization_id": ctx.organization_id, "limit": limit}
    if action:
        sql += " AND action = :action"
        params["action"] = action
    sql += " ORDER BY created_at DESC LIMIT :limit"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


@router.get("/billing/status")
def billing_status(db: Session = Depends(get_sync_session), ctx: TenantContext = Depends(require_permission("billing.view"))):
    row = db.execute(
        text("""
            SELECT plan, status, stripe_customer_id, stripe_subscription_id, trial_ends_at, current_period_end
            FROM subscriptions
            WHERE organization_id=:organization_id
            ORDER BY id DESC LIMIT 1
        """),
        {"organization_id": ctx.organization_id},
    ).mappings().first()
    plan = row["plan"] if row else ctx.plan
    return {"organization_id": ctx.organization_id, "subscription": dict(row) if row else {"plan": plan, "status": "free"}, "limits": PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])}


@router.get("/rbac/permissions")
def rbac_permissions(ctx: TenantContext = Depends(require_permission("admin.access"))):
    from backend.app.enterprise.rbac import ROLE_PERMISSIONS
    return {"roles": {role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()}}


@router.get("/users")
def list_members(db: Session = Depends(get_sync_session), ctx: TenantContext = Depends(require_permission("users.view"))):
    rows = db.execute(text("""
        SELECT u.id, u.email, u.full_name, u.is_active, om.role, om.created_at
        FROM organization_members om JOIN users u ON u.id = om.user_id
        WHERE om.organization_id=:organization_id AND om.is_active=true
        ORDER BY om.created_at ASC
    """), {"organization_id": ctx.organization_id}).mappings().all()
    return [dict(r) for r in rows]

@router.post("/users/invite")
def invite_member(email: str, role: str = "member", full_name: str | None = None, request: Request = None, db: Session = Depends(get_sync_session), ctx: TenantContext = Depends(require_permission("users.invite"))):
    try:
        ensure_feature_allowed(db, organization_id=ctx.organization_id, plan=ctx.plan, feature="users")
    except PlanLimitExceeded as exc:
        raise HTTPException(status_code=403, detail={"detail": "Plan limit reached", "limit": "users", "plan": ctx.plan, "upgrade_required": True, "message": str(exc)})
    if role not in {"admin", "finance_manager", "analyst", "member", "viewer"}:
        raise HTTPException(status_code=400, detail="Role inválida")
    user = db.execute(text("SELECT id FROM users WHERE email=:email"), {"email": email}).mappings().first()
    if not user:
        user_id = new_id()
        db.execute(text("INSERT INTO users (id, email, hashed_password, full_name, is_active) VALUES (:id, :email, :password, :full_name, true)"), {"id": user_id, "email": email, "password": hash_password(new_id()), "full_name": full_name})
    else:
        user_id = str(user["id"])
    exists = db.execute(text("SELECT id FROM organization_members WHERE organization_id=:organization_id AND user_id=:user_id"), {"organization_id": ctx.organization_id, "user_id": user_id}).first()
    if exists:
        raise HTTPException(status_code=400, detail="Usuário já pertence à organização")
    db.execute(text("INSERT INTO organization_members (organization_id, user_id, role, invited_by, is_active) VALUES (:organization_id, :user_id, :role, :invited_by, true)"), {"organization_id": ctx.organization_id, "user_id": user_id, "role": role, "invited_by": ctx.user_id})
    record_event(db, organization_id=ctx.organization_id, user_id=ctx.user_id, action="user.invited", entity_type="user", entity_id=user_id, after={"email": email, "role": role}, ip_address=request.client.host if request and request.client else None, user_agent=request.headers.get("user-agent") if request else None, request_id=getattr(request.state, "request_id", None) if request else None)
    db.commit()
    return {"ok": True, "user_id": user_id, "role": role}

@router.patch("/users/{user_id}/role")
def change_member_role(user_id: str, role: str, request: Request, db: Session = Depends(get_sync_session), ctx: TenantContext = Depends(require_permission("users.manage_roles"))):
    before = db.execute(text("SELECT role FROM organization_members WHERE organization_id=:organization_id AND user_id=:user_id AND is_active=true"), {"organization_id": ctx.organization_id, "user_id": user_id}).mappings().first()
    if not before:
        raise HTTPException(status_code=404, detail="Membro não encontrado")
    db.execute(text("UPDATE organization_members SET role=:role WHERE organization_id=:organization_id AND user_id=:user_id"), {"role": role, "organization_id": ctx.organization_id, "user_id": user_id})
    record_event(db, organization_id=ctx.organization_id, user_id=ctx.user_id, action="user.role_changed", entity_type="user", entity_id=user_id, before=dict(before), after={"role": role}, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {"ok": True}

@router.delete("/users/{user_id}")
def remove_member(user_id: str, request: Request, db: Session = Depends(get_sync_session), ctx: TenantContext = Depends(require_permission("users.remove"))):
    db.execute(text("UPDATE organization_members SET is_active=false WHERE organization_id=:organization_id AND user_id=:user_id"), {"organization_id": ctx.organization_id, "user_id": user_id})
    record_event(db, organization_id=ctx.organization_id, user_id=ctx.user_id, action="user.removed", entity_type="user", entity_id=user_id, ip_address=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"), request_id=getattr(request.state, "request_id", None))
    db.commit()
    return {"ok": True}

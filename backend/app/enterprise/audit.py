from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

SENSITIVE_KEYS = {"password", "token", "refresh_token", "access_token", "secret", "hashed_password"}

def _safe_json(data: Any) -> str | None:
    if data is None:
        return None
    if hasattr(data, "__dict__"):
        data = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
    if isinstance(data, dict):
        data = {k: ("***" if any(s in k.lower() for s in SENSITIVE_KEYS) else v) for k, v in data.items()}
    return json.dumps(data, default=str, ensure_ascii=False)

def record_event(
    db: "Session", *, organization_id: str, user_id: str | None, action: str,
    entity_type: str | None = None, entity_id: str | None = None, before: Any = None, after: Any = None,
    ip_address: str | None = None, user_agent: str | None = None, request_id: str | None = None, commit: bool = False,
) -> None:
    try:
        from sqlalchemy import text
        stmt = text("""
        INSERT INTO audit_logs
        (organization_id, user_id, action, entity_type, entity_id, before_json, after_json, ip_address, user_agent, request_id)
        VALUES (:organization_id, :user_id, :action, :entity_type, :entity_id, :before_json, :after_json, :ip_address, :user_agent, :request_id)
    """)
    except Exception:
        stmt = """
        INSERT INTO audit_logs
        (organization_id, user_id, action, entity_type, entity_id, before_json, after_json, ip_address, user_agent, request_id)
        VALUES (:organization_id, :user_id, :action, :entity_type, :entity_id, :before_json, :after_json, :ip_address, :user_agent, :request_id)
        """
    db.execute(stmt, {
        "organization_id": organization_id, "user_id": user_id, "action": action, "entity_type": entity_type,
        "entity_id": entity_id, "before_json": _safe_json(before), "after_json": _safe_json(after),
        "ip_address": ip_address, "user_agent": user_agent, "request_id": request_id,
    })
    if commit:
        db.commit()

def record_audit_log(db: "Session", **kwargs: Any) -> None:
    action = kwargs.pop("action")
    before = kwargs.pop("before", None)
    after = kwargs.pop("after", None)
    record_event(db, action=action, before=before, after=after, **kwargs)

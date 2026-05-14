
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import json

from sqlalchemy import text

from services.db_session import db_session

MAX_AUTOMATIONS_PER_CYCLE = 3

RULE_PRIORITIES = {
    "health_check": 10,
    "orchestrator_run": 8,
    "market_data_update": 7,
    "catalog_update": 6,
    "intelligence_analysis": 5,
    "bi_refresh": 4,
}

SEVERITY_ORDER = {"critical": 3, "warning": 2, "info": 1}


def _dump(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _load(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def ensure_tables() -> None:
    with db_session() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS automation_rules (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                name TEXT,
                description TEXT,
                rule_type TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                frequency TEXT DEFAULT 'manual',
                last_run_at TEXT,
                next_run_at TEXT,
                parameters_json TEXT,
                created_at TEXT,
                updated_at TEXT,
                priority INTEGER DEFAULT 0,
                execution_window_start TEXT,
                execution_window_end TEXT,
                cooldown_minutes INTEGER DEFAULT 0,
                last_suggestion_at TEXT,
                confidence_score REAL DEFAULT 0,
                severity TEXT DEFAULT 'info',
                dependencies_json TEXT,
                max_runs_per_cycle INTEGER DEFAULT 1,
                safe_auto_enabled BOOLEAN DEFAULT FALSE,
                requires_confirmation BOOLEAN DEFAULT TRUE,
                automation_group TEXT,
                last_blocked_reason TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS automation_runs (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                automation_rule_id INTEGER,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                triggered_by TEXT,
                job_id INTEGER,
                result_json TEXT,
                error_message TEXT,
                confidence_score REAL,
                severity TEXT,
                priority INTEGER,
                skipped_reason TEXT
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_automation_rules_tenant ON automation_rules(tenant_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_automation_runs_tenant ON automation_runs(tenant_id)"))
        db.commit()


def get_default_dependencies(rule_type: str) -> list[str]:
    deps = {
        "market_data_update": ["catalog_update"],
        "intelligence_analysis": ["market_data_update", "orchestrator_run"],
        "bi_refresh": ["intelligence_analysis"],
        "orchestrator_run": ["catalog_update", "market_data_update"],
    }
    return deps.get(rule_type, [])


DEFAULT_RULES = [
    ("Validação de catálogo", "Valida ativos pendentes e qualidade cadastral.", "catalog_update", "smart", "catalog"),
    ("Atualização de dados de mercado", "Atualiza preços, dividendos, índices e macro.", "market_data_update", "smart", "market_data"),
    ("Orquestrador rápido", "Executa ciclo rápido do FinanceOS.", "orchestrator_run", "smart", "analysis"),
    ("Análise inteligente", "Gera leitura inteligente dos resultados.", "intelligence_analysis", "smart", "intelligence"),
    ("Atualização BI", "Atualiza leitura de BI da inteligência.", "bi_refresh", "smart", "bi"),
    ("Health check", "Verifica saúde operacional.", "health_check", "smart", "health"),
]


def create_default_rules(tenant_id: str | None = None) -> None:
    ensure_tables()
    with db_session() as db:
        for name, desc, rule_type, frequency, group in DEFAULT_RULES:
            exists = db.execute(
                text("""
                    SELECT id FROM automation_rules
                    WHERE rule_type=:rule_type AND (:tenant_id IS NULL OR tenant_id=:tenant_id)
                    LIMIT 1
                """),
                {"rule_type": rule_type, "tenant_id": tenant_id},
            ).mappings().first()
            if exists:
                continue
            db.execute(
                text("""
                    INSERT INTO automation_rules
                    (tenant_id, name, description, rule_type, enabled, frequency,
                     parameters_json, created_at, updated_at, priority, severity,
                     dependencies_json, automation_group, safe_auto_enabled, requires_confirmation)
                    VALUES
                    (:tenant_id, :name, :description, :rule_type, true, :frequency,
                     '{}', :now, :now, :priority, 'info',
                     :dependencies_json, :automation_group, :safe_auto_enabled, :requires_confirmation)
                """),
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "description": desc,
                    "rule_type": rule_type,
                    "frequency": frequency,
                    "now": now_iso(),
                    "priority": RULE_PRIORITIES.get(rule_type, 0),
                    "dependencies_json": _dump(get_default_dependencies(rule_type)),
                    "automation_group": group,
                    "safe_auto_enabled": rule_type in ("health_check", "bi_refresh", "intelligence_analysis"),
                    "requires_confirmation": rule_type in ("catalog_update", "market_data_update", "orchestrator_run"),
                },
            )
        db.commit()


def list_rules(tenant_id: str | None = None) -> list[dict[str, Any]]:
    ensure_tables()
    with db_session() as db:
        rows = db.execute(
            text("""
                SELECT *
                FROM automation_rules
                WHERE (:tenant_id IS NULL OR tenant_id=:tenant_id)
                ORDER BY priority DESC, id ASC
            """),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return [dict(r) for r in rows]


def enable_rule(rule_id: int, tenant_id: str | None = None) -> None:
    with db_session() as db:
        db.execute(text("UPDATE automation_rules SET enabled=true, updated_at=:now WHERE id=:id AND (:tenant_id IS NULL OR tenant_id=:tenant_id)"), {"id": int(rule_id), "tenant_id": tenant_id, "now": now_iso()})
        db.commit()


def disable_rule(rule_id: int, tenant_id: str | None = None) -> None:
    with db_session() as db:
        db.execute(text("UPDATE automation_rules SET enabled=false, updated_at=:now WHERE id=:id AND (:tenant_id IS NULL OR tenant_id=:tenant_id)"), {"id": int(rule_id), "tenant_id": tenant_id, "now": now_iso()})
        db.commit()


def update_rule_schedule(rule_id: int, frequency: str, tenant_id: str | None = None) -> None:
    with db_session() as db:
        db.execute(text("UPDATE automation_rules SET frequency=:frequency, updated_at=:now WHERE id=:id AND (:tenant_id IS NULL OR tenant_id=:tenant_id)"), {"id": int(rule_id), "tenant_id": tenant_id, "frequency": frequency, "now": now_iso()})
        db.commit()


def update_rule_safety(rule_id: int, tenant_id: str | None = None, **kwargs) -> None:
    allowed = {"safe_auto_enabled", "requires_confirmation", "cooldown_minutes", "execution_window_start", "execution_window_end"}
    sets = []
    params: dict[str, Any] = {"id": int(rule_id), "tenant_id": tenant_id, "now": now_iso()}
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=:{k}")
            params[k] = v
    if not sets:
        return
    sets.append("updated_at=:now")
    with db_session() as db:
        db.execute(text(f"UPDATE automation_rules SET {', '.join(sets)} WHERE id=:id AND (:tenant_id IS NULL OR tenant_id=:tenant_id)"), params)
        db.commit()


def _last_success(rule_type: str, tenant_id: str | None = None) -> datetime | None:
    with db_session() as db:
        row = db.execute(
            text("""
                SELECT ar.last_run_at
                FROM automation_rules ar
                WHERE ar.rule_type=:rule_type
                  AND ar.last_run_at IS NOT NULL
                  AND (:tenant_id IS NULL OR ar.tenant_id=:tenant_id)
                ORDER BY ar.last_run_at DESC
                LIMIT 1
            """),
            {"rule_type": rule_type, "tenant_id": tenant_id},
        ).mappings().first()
        if not row:
            return None
        try:
            return datetime.fromisoformat(row["last_run_at"])
        except Exception:
            return None


def dependencies_satisfied(rule: dict[str, Any], tenant_id: str | None = None) -> tuple[bool, str | None]:
    deps = _load(rule.get("dependencies_json"))
    if not deps:
        return True, None
    for dep in deps:
        last = _last_success(dep, tenant_id)
        if not last:
            return False, f"dependency_not_satisfied:{dep}"
    return True, None


def can_run_in_safe_mode(rule: dict[str, Any]) -> bool:
    return rule.get("rule_type") in ("health_check", "bi_refresh", "intelligence_analysis")


def _cooldown(rule: dict[str, Any]) -> tuple[bool, int]:
    cooldown = int(rule.get("cooldown_minutes") or 0)
    if cooldown <= 0 or not rule.get("last_suggestion_at"):
        return False, 0
    try:
        last = datetime.fromisoformat(rule["last_suggestion_at"])
        remaining = cooldown - int((datetime.utcnow() - last).total_seconds() / 60)
        return remaining > 0, max(0, remaining)
    except Exception:
        return False, 0


def evaluate_rules(tenant_id: str | None = None) -> list[dict[str, Any]]:
    create_default_rules(tenant_id)
    rules = list_rules(tenant_id)
    suggestions = []
    for rule in rules:
        enabled = bool(rule.get("enabled"))
        deps_ok, blocked_reason = dependencies_satisfied(rule, tenant_id)
        cooldown_active, cooldown_remaining = _cooldown(rule)
        should_run = enabled and deps_ok and not cooldown_active
        severity = rule.get("severity") or "info"
        confidence = float(rule.get("confidence_score") or 0)
        if should_run:
            confidence = max(confidence, 55.0)
            severity = "warning" if rule.get("rule_type") in ("market_data_update", "orchestrator_run") else severity

        item = {
            "rule_id": rule["id"],
            "rule_type": rule.get("rule_type"),
            "name": rule.get("name"),
            "should_run": should_run,
            "blocked": not deps_ok,
            "blocked_reason": blocked_reason,
            "dependencies": _load(rule.get("dependencies_json")),
            "selected_for_cycle": False,
            "waiting_next_cycle": False,
            "safe_auto_enabled": bool(rule.get("safe_auto_enabled")),
            "requires_confirmation": bool(rule.get("requires_confirmation")),
            "confidence_score": confidence,
            "severity": severity,
            "priority": int(rule.get("priority") or 0),
            "cooldown_active": cooldown_active,
            "cooldown_remaining_minutes": cooldown_remaining,
            "reason": blocked_reason or ("Regra em cooldown" if cooldown_active else rule.get("description")),
            "action": rule.get("rule_type"),
        }
        suggestions.append(item)

    suggestions.sort(key=lambda s: (SEVERITY_ORDER.get(s["severity"], 0), s["priority"], s["confidence_score"]), reverse=True)
    selected = 0
    for item in suggestions:
        if item["should_run"] and selected < MAX_AUTOMATIONS_PER_CYCLE:
            item["selected_for_cycle"] = True
            selected += 1
        elif item["should_run"]:
            item["waiting_next_cycle"] = True
    return suggestions


def apply_cycle_limits(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = 0
    for item in suggestions:
        item["selected_for_cycle"] = False
        item["waiting_next_cycle"] = False
        if item.get("should_run") and selected < MAX_AUTOMATIONS_PER_CYCLE:
            item["selected_for_cycle"] = True
            selected += 1
        elif item.get("should_run"):
            item["waiting_next_cycle"] = True
    return suggestions


def get_blocked_automation_suggestions(tenant_id: str | None = None) -> list[dict[str, Any]]:
    return [s for s in evaluate_rules(tenant_id) if s.get("blocked")]


def log_automation_run(rule_id: int, status: str, tenant_id: str | None = None, **kwargs) -> int:
    with db_session() as db:
        row = db.execute(
            text("""
                INSERT INTO automation_runs
                (tenant_id, automation_rule_id, status, started_at, finished_at, triggered_by,
                 job_id, result_json, error_message, confidence_score, severity, priority, skipped_reason)
                VALUES
                (:tenant_id, :rule_id, :status, :started_at, :finished_at, :triggered_by,
                 :job_id, :result_json, :error_message, :confidence_score, :severity, :priority, :skipped_reason)
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "rule_id": int(rule_id),
                "status": status,
                "started_at": kwargs.get("started_at", now_iso()),
                "finished_at": kwargs.get("finished_at"),
                "triggered_by": kwargs.get("triggered_by", "manual"),
                "job_id": kwargs.get("job_id"),
                "result_json": _dump(kwargs.get("result")),
                "error_message": kwargs.get("error_message"),
                "confidence_score": kwargs.get("confidence_score"),
                "severity": kwargs.get("severity"),
                "priority": kwargs.get("priority"),
                "skipped_reason": kwargs.get("skipped_reason"),
            },
        ).mappings().first()
        db.commit()
        return int(row["id"])


def run_rule(rule_id: int, tenant_id: str | None = None, triggered_by: str = "manual", force_outside_window: bool = False, ignore_cooldown: bool = False) -> dict[str, Any]:
    ensure_tables()
    with db_session() as db:
        rule = db.execute(
            text("SELECT * FROM automation_rules WHERE id=:id AND (:tenant_id IS NULL OR tenant_id=:tenant_id)"),
            {"id": int(rule_id), "tenant_id": tenant_id},
        ).mappings().first()
        if not rule:
            return {"status": "failed", "error": "Regra não encontrada"}
        rule = dict(rule)

    deps_ok, reason = dependencies_satisfied(rule, tenant_id)
    if not deps_ok:
        log_automation_run(rule_id, "skipped", tenant_id, skipped_reason=reason, error_message=reason)
        return {"status": "skipped", "error": reason}

    cooldown_active, remaining = _cooldown(rule)
    if cooldown_active and not ignore_cooldown:
        msg = f"Regra em cooldown por {remaining} minuto(s)."
        log_automation_run(rule_id, "skipped", tenant_id, skipped_reason="cooldown", error_message=msg)
        return {"status": "skipped", "error": msg}

    from services.background_jobs import create_job
    job_type_map = {
        "catalog_update": "catalog_pipeline",
        "market_data_update": "market_data_pipeline",
        "orchestrator_run": "financeos_orchestrator",
        "intelligence_analysis": "intelligence_analysis",
        "bi_refresh": "bi_refresh",
        "health_check": "health_check",
    }
    job_type = job_type_map.get(rule.get("rule_type"), rule.get("rule_type"))
    try:
        job_id = create_job(job_type, _load(rule.get("parameters_json")), priority=int(rule.get("priority") or 0), tenant_id=tenant_id)
        with db_session() as db:
            db.execute(text("UPDATE automation_rules SET last_run_at=:now, last_suggestion_at=:now WHERE id=:id"), {"now": now_iso(), "id": int(rule_id)})
            db.commit()
        log_automation_run(rule_id, "success", tenant_id, job_id=job_id, result={"job_type": job_type}, confidence_score=rule.get("confidence_score"), severity=rule.get("severity"), priority=rule.get("priority"))
        return {"status": "success", "job_id": job_id}
    except Exception as exc:
        log_automation_run(rule_id, "failed", tenant_id, error_message=str(exc))
        return {"status": "failed", "error": str(exc)}


def list_automation_runs(tenant_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_tables()
    with db_session() as db:
        rows = db.execute(
            text("""
                SELECT arun.*, ar.name AS rule_name, ar.rule_type
                FROM automation_runs arun
                LEFT JOIN automation_rules ar ON ar.id = arun.automation_rule_id
                WHERE (:tenant_id IS NULL OR arun.tenant_id=:tenant_id)
                ORDER BY arun.id DESC
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "limit": int(limit)},
        ).mappings().all()
        return [dict(r) for r in rows]


def automation_summary(tenant_id: str | None = None) -> dict[str, Any]:
    suggestions = evaluate_rules(tenant_id)
    return {
        "critical_suggestions": len([s for s in suggestions if s.get("severity") == "critical"]),
        "warning_suggestions": len([s for s in suggestions if s.get("severity") == "warning"]),
        "cooldown_suggestions": len([s for s in suggestions if s.get("cooldown_active")]),
        "blocked_suggestions": len([s for s in suggestions if s.get("blocked")]),
        "waiting_next_cycle": len([s for s in suggestions if s.get("waiting_next_cycle")]),
        "most_urgent": suggestions[0] if suggestions else None,
    }


from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]


def _check(name: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message, "details": details or {}}


def check_postgres() -> dict[str, Any]:
    try:
        from db.database import SessionLocal
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return _check("postgres", "pass", "Conexão PostgreSQL OK")
    except Exception as exc:
        return _check("postgres", "fail", f"Postgres indisponível: {exc}")


def check_redis() -> dict[str, Any]:
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        return _check("redis", "pass", "Redis OK")
    except Exception as exc:
        return _check("redis", "warn", f"Redis indisponível: {exc}")


def check_mlflow() -> dict[str, Any]:
    uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    try:
        resp = requests.get(uri, timeout=3)
        if resp.status_code < 500:
            return _check("mlflow", "pass", f"MLflow respondeu em {uri}")
        return _check("mlflow", "warn", f"MLflow respondeu HTTP {resp.status_code}")
    except Exception as exc:
        return _check("mlflow", "warn", f"MLflow indisponível: {exc}")


def check_celery() -> dict[str, Any]:
    try:
        from workers.celery_app import app
        insp = app.control.inspect(timeout=2)
        active = insp.active() or {}
        if active:
            return _check("celery", "pass", "Celery worker ativo", {"workers": list(active.keys())})
        return _check("celery", "warn", "Celery sem workers ativos")
    except Exception as exc:
        return _check("celery", "warn", f"Celery indisponível: {exc}")


def check_env_secrets() -> dict[str, Any]:
    env = os.getenv("FINANCEOS_ENV", "development")
    secret = os.getenv("SECRET_KEY", "")
    database_url = os.getenv("DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")
    stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")

    bad_values = {"", "change-me-in-production", "CHANGE_THIS_SECRET_IN_PRODUCTION", "dev", "secret", "changeme"}
    problems = []
    if secret in bad_values or len(secret) < 32:
        problems.append("SECRET_KEY inválida ou curta demais")
    if not database_url:
        problems.append("DATABASE_URL ausente")
    if env == "production" and not redis_url:
        problems.append("REDIS_URL ausente em produção")
    if env == "production" and (not stripe_secret or stripe_secret in bad_values):
        problems.append("STRIPE_SECRET_KEY ausente/insegura em produção")

    if problems:
        return _check("secrets", "fail" if env == "production" else "warn", "; ".join(problems))
    return _check("secrets", "pass", "Secrets essenciais OK")


def check_auth_config() -> dict[str, Any]:
    try:
        from services.auth_middleware import DEV_MODE
        if os.getenv("FINANCEOS_ENV") == "production" and DEV_MODE:
            return _check("auth", "fail", "FINANCEOS_DEV_MODE não pode estar ativo em produção")
        return _check("auth", "pass", "Configuração de auth OK")
    except Exception as exc:
        return _check("auth", "fail", f"Auth quebrado: {exc}")


def check_storage_paths() -> dict[str, Any]:
    required = [ROOT / "ml" / "models", ROOT / "ml" / "datasets", ROOT / "ml" / "predictions"]
    missing = []
    for path in required:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test = path / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
        except Exception as exc:
            missing.append(f"{path}: {exc}")
    if missing:
        return _check("storage", "warn", "Problemas em paths de storage", {"issues": missing})
    return _check("storage", "pass", "Storage local OK")


def check_stripe() -> dict[str, Any]:
    env = os.getenv("FINANCEOS_ENV", "development")
    key = os.getenv("STRIPE_SECRET_KEY", "")
    webhook = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if env == "production" and (not key or not webhook):
        return _check("stripe", "fail", "Stripe não configurado em produção")
    if not key or not webhook:
        return _check("stripe", "warn", "Stripe incompleto em ambiente não produção")
    return _check("stripe", "pass", "Stripe configurado")


def check_jobs() -> dict[str, Any]:
    try:
        from db.database import SessionLocal
        with SessionLocal() as db:
            try:
                row = db.execute(text("SELECT COUNT(*) AS total FROM background_jobs WHERE status='running'")).mappings().first()
                return _check("jobs", "pass", "Tabela de jobs acessível", {"running": int(row["total"] or 0)})
            except Exception:
                return _check("jobs", "warn", "Tabela background_jobs indisponível ou ainda não migrada")
    except Exception as exc:
        return _check("jobs", "warn", f"Jobs não verificáveis: {exc}")


def check_sqlite_disabled() -> dict[str, Any]:
    allowed_files = {
        "scripts/migrate_sqlite_to_postgres.py",
        "scripts/production_readiness_check.py",
        "PATCH_48_3_SQLITE_SCAN.json",
    }
    hits = []
    forbidden_terms = ["sql" + "ite3", "financas" + ".db", "data/" + "financas" + ".db", "sql" + "ite+aiosqlite"]
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(ROOT))
        if rel in allowed_files:
            continue
        txt = path.read_text(encoding="utf-8", errors="ignore")
        if any(term in txt for term in forbidden_terms):
            hits.append(rel)
    if hits:
        status = "fail" if os.getenv("FINANCEOS_ENV", "development") == "production" else "warn"
        return _check("sqlite_disabled", status, "SQLite residual detectado", {"files": hits})
    return _check("sqlite_disabled", "pass", "Nenhum uso SQLite em runtime detectado")


def check_sqlite_residual() -> dict[str, Any]:
    return check_sqlite_disabled()

def run_full_healthcheck() -> dict[str, Any]:
    checks = [
        check_postgres(),
        check_redis(),
        check_mlflow(),
        check_celery(),
        check_env_secrets(),
        check_auth_config(),
        check_storage_paths(),
        check_stripe(),
        check_jobs(),
        check_sqlite_disabled(),
    ]
    if any(c["status"] == "fail" for c in checks):
        status = "fail"
    elif any(c["status"] == "warn" for c in checks):
        status = "warn"
    else:
        status = "pass"
    return {"status": status, "checks": checks}

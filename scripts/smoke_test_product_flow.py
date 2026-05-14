
from __future__ import annotations

import argparse
import uuid
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from db.database import SessionLocal
from services.plan_guard import get_tenant_plan
from services.investor_service import get_opportunities
from services.production_health_service import run_full_healthcheck


ESSENTIAL_TABLES = [
    "tenants", "users", "portfolio_accounts", "portfolio_transactions",
    "asset_catalog", "ml_models", "ml_predictions", "backtest_runs",
    "orchestrator_runs", "automation_rules",
]


def table_exists(db, table: str) -> bool:
    row = db.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:table
            ) AS exists
        """),
        {"table": table},
    ).mappings().first()
    return bool(row["exists"]) if row else False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    failures = []
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with SessionLocal() as db:
        try:
            db.execute(text("SELECT 1"))
            print("PASS banco conectado")
        except Exception as exc:
            print("FAIL banco:", exc)
            return 2

        for table in ESSENTIAL_TABLES:
            if table_exists(db, table):
                print(f"PASS tabela {table}")
            else:
                print(f"FAIL tabela {table} ausente")
                failures.append(f"missing_table:{table}")

        try:
            db.execute(
                text("INSERT INTO tenants (id, name, slug, plan) VALUES (:id, 'Smoke Tenant', :slug, 'free')"),
                {"id": tenant_id, "slug": f"smoke-{tenant_id[:8]}"},
            )
            db.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, hashed_password, full_name, role, plan)
                    VALUES (:id, :tenant_id, :email, 'hash', 'Smoke User', 'admin', 'free')
                """),
                {"id": user_id, "tenant_id": tenant_id, "email": f"smoke-{tenant_id[:8]}@local.test"},
            )
            row = db.execute(text("SELECT id FROM tenants WHERE id=:id"), {"id": tenant_id}).first()
            print("PASS tenant fake rollback" if row else "FAIL tenant fake")
            row = db.execute(text("SELECT id FROM users WHERE id=:id"), {"id": user_id}).first()
            print("PASS user fake rollback" if row else "FAIL user fake")
            db.rollback()
        except Exception as exc:
            failures.append(f"fake_create:{exc}")
            print("FAIL criação fake:", exc)
            db.rollback()

    try:
        plan = get_tenant_plan(tenant_id)
        print("PASS consulta plano:", plan)
    except Exception as exc:
        failures.append(f"plan:{exc}")
        print("FAIL consulta plano:", exc)

    try:
        opps = get_opportunities(tenant_id=tenant_id, limit=10)
        print("PASS consulta oportunidades:", len(opps))
    except Exception as exc:
        failures.append(f"opportunities:{exc}")
        print("FAIL oportunidades:", exc)

    health = run_full_healthcheck()
    print("PASS healthcheck executado:", health.get("status"))

    if failures:
        print("FAILURES:", failures)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

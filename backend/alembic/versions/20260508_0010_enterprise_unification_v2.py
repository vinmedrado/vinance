"""Enterprise backend unification v2

Revision ID: 20260508_0010
Revises: 20260508_0009
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260508_0010"
down_revision = "20260508_0009"
branch_labels = None
depends_on = None

ROLES = {
    "owner": ["*"],
    "admin": ["expenses.view","expenses.create","expenses.edit","expenses.delete","incomes.view","incomes.create","incomes.edit","incomes.delete","budgets.view","budgets.manage","goals.view","goals.create","goals.edit","goals.delete","accounts.view","accounts.manage","cards.view","cards.manage","investments.view","investments.manage","portfolio.view","portfolio.manage","alerts.view","alerts.manage","diagnosis.view","jobs.view","jobs.run","admin.access","billing.view","billing.manage","users.view","users.invite","users.manage_roles","users.remove","analytics.view","audit.view","health.admin"],
    "finance_manager": ["expenses.view","expenses.create","expenses.edit","incomes.view","incomes.create","incomes.edit","budgets.view","budgets.manage","goals.view","goals.create","goals.edit","accounts.view","accounts.manage","cards.view","cards.manage","investments.view","portfolio.view","alerts.view","alerts.manage","diagnosis.view","analytics.view","audit.view"],
    "analyst": ["expenses.view","incomes.view","budgets.view","goals.view","accounts.view","cards.view","investments.view","portfolio.view","alerts.view","diagnosis.view","jobs.view","analytics.view"],
    "member": ["expenses.view","expenses.create","expenses.edit","incomes.view","incomes.create","incomes.edit","budgets.view","goals.view","goals.create","goals.edit","accounts.view","cards.view","investments.view","portfolio.view","alerts.view","diagnosis.view"],
    "viewer": ["expenses.view","incomes.view","budgets.view","goals.view","accounts.view","cards.view","investments.view","portfolio.view","alerts.view","diagnosis.view"],
}

def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())

def _cols(table):
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(table)} if table in _tables() else set()

def _add_column_if_missing(table: str, column: sa.Column):
    if table in _tables() and column.name not in _cols(table):
        op.add_column(table, column)

def _idx_if_missing(name, table, cols):
    if table not in _tables(): return
    existing={i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing: op.create_index(name, table, cols)

def upgrade() -> None:
    bind = op.get_bind()
    if "users" not in _tables():
        op.create_table("users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("email_verified_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True)),
            sa.Column("tenant_id", sa.String(36)),
            sa.Column("role", sa.String(80)),
            sa.Column("plan", sa.String(40)),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
    else:
        _add_column_if_missing("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
        _add_column_if_missing("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
        _add_column_if_missing("users", sa.Column("tenant_id", sa.String(36)))
        _add_column_if_missing("users", sa.Column("role", sa.String(80)))
        _add_column_if_missing("users", sa.Column("plan", sa.String(40)))
    _idx_if_missing("ix_users_email", "users", ["email"])
    _idx_if_missing("ix_users_tenant_id", "users", ["tenant_id"])

    if "enterprise_users" in _tables():
        bind.execute(sa.text("""
            INSERT INTO users (id, email, hashed_password, full_name, is_active, email_verified_at, created_at, last_login_at)
            SELECT id, email, hashed_password, full_name, is_active, email_verified_at, created_at, last_login_at
            FROM enterprise_users eu
            WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = eu.id OR u.email = eu.email)
        """))

    _add_column_if_missing("audit_logs", sa.Column("request_id", sa.String(80)))
    _idx_if_missing("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    for table in ["erp_accounts","erp_cards","erp_categories","erp_incomes","erp_expenses","erp_budgets","erp_planned_investments","erp_alerts","financial_goals","background_jobs","analytics_events","audit_logs","enterprise_jobs","subscriptions"]:
        if table in _tables():
            _add_column_if_missing(table, sa.Column("organization_id", sa.String(36)))
            _idx_if_missing(f"ix_{table}_organization_id_v2", table, ["organization_id"])

    for role, perms in ROLES.items():
        bind.execute(sa.text("INSERT INTO roles (name, description) VALUES (:name, :description) ON CONFLICT (name) DO NOTHING"), {"name": role, "description": f"Default {role} role"})
        for perm in perms:
            if perm == "*": continue
            bind.execute(sa.text("INSERT INTO permissions (name, description) VALUES (:name, :description) ON CONFLICT (name) DO NOTHING"), {"name": perm, "description": perm})
            bind.execute(sa.text("INSERT INTO role_permissions (role_name, permission_name) VALUES (:role, :perm) ON CONFLICT (role_name, permission_name) DO NOTHING"), {"role": role, "perm": perm})


def downgrade() -> None:
    pass

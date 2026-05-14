"""Enterprise multi-tenant backend foundation

Revision ID: 20260508_0009
Revises: 20260507_0008
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260508_0009"
down_revision = "20260507_0008"
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(table)} if table in inspector.get_table_names() else set()
    if column.name not in existing:
        op.add_column(table, column)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table in inspector.get_table_names():
        existing = {idx["name"] for idx in inspector.get_indexes(table)}
        if name not in existing:
            op.create_index(name, table, columns)


def upgrade() -> None:
    op.create_table("organizations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("slug", sa.String(120), nullable=False), sa.Column("plan", sa.String(40), nullable=False, server_default="free"), sa.Column("subscription_status", sa.String(40), nullable=False, server_default="trialing"), sa.Column("stripe_customer_id", sa.String(255)), sa.Column("stripe_subscription_id", sa.String(255)), sa.Column("trial_ends_at", sa.DateTime(timezone=True)), sa.Column("current_period_end", sa.DateTime(timezone=True)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("slug", name="uq_organizations_slug"))
    op.create_table("enterprise_users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(255), nullable=False), sa.Column("hashed_password", sa.String(255), nullable=False), sa.Column("full_name", sa.String(255)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("email_verified_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("email", name="uq_enterprise_users_email"))
    op.create_table("roles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(80), nullable=False), sa.Column("description", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("name", name="uq_roles_name"))
    op.create_table("permissions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("name", name="uq_permissions_name"))
    op.create_table("role_permissions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("role_name", sa.String(80), nullable=False), sa.Column("permission_name", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("role_name", "permission_name", name="uq_role_permission"))
    op.create_table("organization_members", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("role", sa.String(80), nullable=False, server_default="member"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("invited_by", sa.String(36)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_user"))
    op.create_table("subscriptions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.String(36), nullable=False), sa.Column("plan", sa.String(40), nullable=False, server_default="free"), sa.Column("status", sa.String(40), nullable=False, server_default="trialing"), sa.Column("stripe_customer_id", sa.String(255)), sa.Column("stripe_subscription_id", sa.String(255)), sa.Column("trial_ends_at", sa.DateTime(timezone=True)), sa.Column("current_period_end", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("tenant_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.String(36), nullable=False), sa.Column("key", sa.String(120), nullable=False), sa.Column("value_json", sa.Text()), sa.Column("updated_by", sa.String(36)), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("organization_id", "key", name="uq_tenant_setting_key"))
    op.create_table("user_sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36)), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("refresh_token_hash", sa.String(128), nullable=False), sa.Column("ip_address", sa.String(80)), sa.Column("user_agent", sa.String(500)), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("refresh_token_hash", name="uq_user_sessions_refresh_hash"))
    op.create_table("refresh_tokens", sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36)), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("session_id", sa.String(36)), sa.Column("token_hash", sa.String(128), nullable=False), sa.Column("replaced_by_hash", sa.String(128)), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"))
    op.create_table("password_reset_tokens", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("token_hash", sa.String(128), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("token_hash", name="uq_password_reset_hash"))
    op.create_table("email_verification_tokens", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), nullable=False), sa.Column("token_hash", sa.String(128), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("token_hash", name="uq_email_verification_hash"))
    op.create_table("audit_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36)), sa.Column("action", sa.String(120), nullable=False), sa.Column("entity_type", sa.String(120)), sa.Column("entity_id", sa.String(120)), sa.Column("before_json", sa.Text()), sa.Column("after_json", sa.Text()), sa.Column("ip_address", sa.String(80)), sa.Column("user_agent", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("enterprise_jobs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.String(36), nullable=False), sa.Column("created_by", sa.String(36)), sa.Column("job_type", sa.String(120), nullable=False), sa.Column("status", sa.String(40), nullable=False, server_default="queued"), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.Column("parameters_json", sa.Text()), sa.Column("result_json", sa.Text()), sa.Column("error_message", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    for table in ["erp_accounts", "erp_cards", "erp_categories", "erp_incomes", "erp_expenses", "erp_budgets", "erp_planned_investments", "erp_alerts", "financial_goals", "background_jobs", "analytics_events"]:
        _add_column_if_missing(table, sa.Column("organization_id", sa.String(36), nullable=True))
        _add_column_if_missing(table, sa.Column("created_by", sa.String(36), nullable=True))
        _add_column_if_missing(table, sa.Column("updated_by", sa.String(36), nullable=True))
        _add_column_if_missing(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        _create_index_if_missing(f"ix_{table}_organization_id", table, ["organization_id"])


def downgrade() -> None:
    for table in ["enterprise_jobs", "audit_logs", "email_verification_tokens", "password_reset_tokens", "refresh_tokens", "user_sessions", "tenant_settings", "subscriptions", "organization_members", "role_permissions", "permissions", "roles", "enterprise_users", "organizations"]:
        op.drop_table(table)

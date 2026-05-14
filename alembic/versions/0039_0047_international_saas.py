
"""FinanceOS international SaaS foundation

Revision ID: 0039_0047_international
Revises:
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039_0047_international"
down_revision = None
branch_labels = None
depends_on = None


def _uuid():
    return postgresql.UUID(as_uuid=True)


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "tenants",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("max_assets", sa.Integer, server_default="50"),
        sa.Column("max_backtests", sa.Integer, server_default="10"),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "users",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", sa.String(50), server_default="investor"),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("preferred_language", sa.String(10), server_default="pt_BR"),
        sa.Column("preferred_currency", sa.String(10), server_default="BRL"),
        sa.Column("onboarding_completed", sa.Boolean, server_default=sa.text("FALSE")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("last_login", sa.DateTime(timezone=True)),
    )

    tenant_tables = [
        "assets", "asset_catalog", "asset_prices", "asset_dividends", "asset_analysis_metrics", "asset_scores",
        "backtest_runs", "backtest_metrics", "backtest_trades", "backtest_equity_curve",
        "optimization_runs", "optimization_results",
        "ml_datasets", "ml_models", "ml_predictions", "ml_runs", "ml_model_evaluations",
        "market_indices", "macro_indicators", "data_sync_logs", "catalog_pipeline_runs",
        "market_data_pipeline_runs", "background_jobs", "automation_rules", "automation_runs",
    ]
    for table in tenant_tables:
        op.execute(f'CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY)')
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id UUID')
        op.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_tenant_id ON {table}(tenant_id)')

    op.create_table(
        "subscription_plans",
        sa.Column("slug", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_brl_monthly", sa.Integer, nullable=False),
        sa.Column("max_assets", sa.Integer, nullable=False),
        sa.Column("max_backtests", sa.Integer, nullable=False),
        sa.Column("max_ml_models", sa.Integer, nullable=False),
        sa.Column("alerts_enabled", sa.Boolean, server_default=sa.text("FALSE")),
        sa.Column("api_access", sa.Boolean, server_default=sa.text("FALSE")),
    )
    op.execute("""
        INSERT INTO subscription_plans
        (slug, name, price_brl_monthly, max_assets, max_backtests, max_ml_models, alerts_enabled, api_access)
        VALUES
        ('free', 'Gratuito / Free', 0, 50, 5, 3, false, false),
        ('pro', 'Pro', 49, 500, 50, 20, true, false),
        ('enterprise', 'Enterprise', 199, 9999, 999, 999, true, true)
        ON CONFLICT (slug) DO NOTHING
    """)

    op.create_table(
        "api_keys",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("permissions", postgresql.JSONB, server_default=sa.text("'[\"read\"]'::jsonb")),
        sa.Column("rate_limit_per_hour", sa.Integer, server_default="1000"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "portfolio_accounts",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("broker", sa.String(100)),
        sa.Column("currency", sa.String(10), server_default="BRL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_table(
        "portfolio_transactions",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", _uuid(), nullable=False),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("ticker", sa.String(30), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), server_default="0"),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("exchange", sa.String(50)),
        sa.Column("currency", sa.String(10), server_default="BRL"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", _uuid(), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("total_value_brl", sa.Numeric(20, 8)),
        sa.Column("cash_brl", sa.Numeric(20, 8), server_default="0"),
        sa.Column("positions", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_table(
        "ml_drift_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("model_id", sa.Integer),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("drift_score", sa.Float),
        sa.Column("drifted_features", postgresql.JSONB),
        sa.Column("action_taken", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_table(
        "user_alerts",
        sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("ticker", sa.String(30)),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("condition_json", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("TRUE")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
        sa.Column("channel", sa.String(20), server_default="email"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade():
    for table in ["user_alerts", "ml_drift_reports", "portfolio_snapshots", "portfolio_transactions", "portfolio_accounts", "api_keys", "subscription_plans", "users", "tenants"]:
        op.drop_table(table)

"""Budget advisor flow snapshots and indexes.

Revision ID: 20260508_0013
Revises: 20260508_0012
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260508_0013"
down_revision = "20260508_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_advisor_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("recommended_model", sa.String(length=60), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("investment_capacity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_budget_advisor_snapshots_org_period", "budget_advisor_snapshots", ["organization_id", "year", "month"])
    op.create_index("ix_budget_advisor_snapshots_organization_id", "budget_advisor_snapshots", ["organization_id"])
    op.create_index("ix_erp_expenses_org_status_due", "erp_expenses", ["organization_id", "status", "due_date"])
    op.create_index("ix_erp_incomes_org_received", "erp_incomes", ["organization_id", "received_at"])


def downgrade() -> None:
    try:
        op.drop_index("ix_erp_incomes_org_received", table_name="erp_incomes")
        op.drop_index("ix_erp_expenses_org_status_due", table_name="erp_expenses")
    except Exception:
        pass
    op.drop_index("ix_budget_advisor_snapshots_organization_id", table_name="budget_advisor_snapshots")
    op.drop_index("ix_budget_advisor_snapshots_org_period", table_name="budget_advisor_snapshots")
    op.drop_table("budget_advisor_snapshots")

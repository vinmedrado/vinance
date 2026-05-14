"""quant intelligence goals engine

Revision ID: 20260508_0012
Revises: 20260508_0011
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0012"
down_revision = "20260508_0011"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "financial_goals_engine",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_type", sa.String(length=60), nullable=False, server_default="custom"),
        sa.Column("target_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("current_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("monthly_contribution", sa.Float(), nullable=False, server_default="0"),
        sa.Column("inflation_adjusted_target", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_profile", sa.String(length=40), nullable=False, server_default="moderate"),
        sa.Column("investment_horizon", sa.String(length=40), nullable=False, server_default="medium_term"),
        sa.Column("success_probability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_completion_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_financial_goals_engine_org_user", "financial_goals_engine", ["organization_id", "user_id"])
    op.create_index("ix_financial_goals_engine_org_deleted", "financial_goals_engine", ["organization_id", "deleted_at"])

def downgrade():
    op.drop_index("ix_financial_goals_engine_org_deleted", table_name="financial_goals_engine")
    op.drop_index("ix_financial_goals_engine_org_user", table_name="financial_goals_engine")
    op.drop_table("financial_goals_engine")

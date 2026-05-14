"""Intelligent investing profiles and recommendation snapshots.

Revision ID: 20260508_0011
Revises: 20260508_0010
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260508_0011"
down_revision = "20260508_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("monthly_income", sa.Float(), nullable=False, server_default="0"),
        sa.Column("monthly_expenses", sa.Float(), nullable=False, server_default="0"),
        sa.Column("available_to_invest", sa.Float(), nullable=False, server_default="0"),
        sa.Column("emergency_reserve_months", sa.Float(), nullable=False, server_default="0"),
        sa.Column("risk_profile", sa.String(length=40), nullable=False, server_default="moderate"),
        sa.Column("investment_experience", sa.String(length=40), nullable=False, server_default="beginner"),
        sa.Column("financial_goal", sa.String(length=120), nullable=True),
        sa.Column("target_amount", sa.Float(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("preferred_markets", sa.Text(), nullable=True),
        sa.Column("liquidity_preference", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("dividend_preference", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("volatility_tolerance", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("investment_horizon", sa.String(length=40), nullable=False, server_default="medium_term"),
        sa.Column("monthly_investment_capacity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_financial_profiles_org_user"),
    )
    op.create_index("ix_financial_profiles_org_deleted", "financial_profiles", ["organization_id", "deleted_at"])
    op.create_index("ix_financial_profiles_organization_id", "financial_profiles", ["organization_id"])
    op.create_index("ix_financial_profiles_user_id", "financial_profiles", ["user_id"])

    op.create_table(
        "intelligent_recommendation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("financial_profile_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_json", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendation_snapshots_org_created", "intelligent_recommendation_snapshots", ["organization_id", "created_at"])
    op.create_index("ix_intelligent_recommendation_snapshots_organization_id", "intelligent_recommendation_snapshots", ["organization_id"])
    op.create_index("ix_intelligent_recommendation_snapshots_user_id", "intelligent_recommendation_snapshots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_intelligent_recommendation_snapshots_user_id", table_name="intelligent_recommendation_snapshots")
    op.drop_index("ix_intelligent_recommendation_snapshots_organization_id", table_name="intelligent_recommendation_snapshots")
    op.drop_index("ix_recommendation_snapshots_org_created", table_name="intelligent_recommendation_snapshots")
    op.drop_table("intelligent_recommendation_snapshots")
    op.drop_index("ix_financial_profiles_user_id", table_name="financial_profiles")
    op.drop_index("ix_financial_profiles_organization_id", table_name="financial_profiles")
    op.drop_index("ix_financial_profiles_org_deleted", table_name="financial_profiles")
    op.drop_table("financial_profiles")

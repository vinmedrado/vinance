"""create financial tables

Revision ID: 0002_create_financial_tables
Revises: 0001_create_users
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_create_financial_tables"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incomes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("income_type", sa.String(length=80), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incomes_user_id", "incomes", ["user_id"])
    op.create_index("ix_incomes_received_at", "incomes", ["received_at"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])
    op.create_index("ix_expenses_category", "expenses", ["category"])
    op.create_index("ix_expenses_due_date", "expenses", ["due_date"])
    op.create_index("ix_expenses_is_paid", "expenses", ["is_paid"])

    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monthly_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("emergency_reserve", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("has_debt_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("risk_profile", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_financial_profiles_user_id", "financial_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_financial_profiles_user_id", table_name="financial_profiles")
    op.drop_table("financial_profiles")
    op.drop_index("ix_expenses_is_paid", table_name="expenses")
    op.drop_index("ix_expenses_due_date", table_name="expenses")
    op.drop_index("ix_expenses_category", table_name="expenses")
    op.drop_index("ix_expenses_user_id", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_incomes_received_at", table_name="incomes")
    op.drop_index("ix_incomes_user_id", table_name="incomes")
    op.drop_table("incomes")

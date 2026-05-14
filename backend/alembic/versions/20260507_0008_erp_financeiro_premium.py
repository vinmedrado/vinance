"""ERP financeiro premium tables

Revision ID: 20260507_0008
Revises: 20260429_0007
Create Date: 2026-05-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260507_0008"
down_revision = "20260429_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("erp_accounts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(140), nullable=False), sa.Column("type", sa.String(40), nullable=False, server_default="checking"), sa.Column("institution", sa.String(140)), sa.Column("balance", sa.Float(), nullable=False, server_default="0"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_erp_accounts_user_active", "erp_accounts", ["user_id", "is_active"])
    op.create_table("erp_cards", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(140), nullable=False), sa.Column("brand", sa.String(60)), sa.Column("limit_amount", sa.Float(), nullable=False, server_default="0"), sa.Column("closing_day", sa.Integer()), sa.Column("due_day", sa.Integer()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("erp_categories", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("kind", sa.String(20), nullable=False, server_default="expense"), sa.Column("group", sa.String(40)), sa.Column("color", sa.String(30)), sa.UniqueConstraint("user_id", "name", "kind", name="uq_erp_categories_user_name_kind"))
    op.create_table("erp_incomes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("description", sa.String(220), nullable=False), sa.Column("category_id", sa.Integer()), sa.Column("account_id", sa.Integer()), sa.Column("received_at", sa.Date(), nullable=False), sa.Column("recurrence", sa.String(40), nullable=False, server_default="none"), sa.Column("status", sa.String(20), nullable=False, server_default="received"), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_erp_incomes_user_date", "erp_incomes", ["user_id", "received_at"])
    op.create_table("erp_expenses", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("description", sa.String(220), nullable=False), sa.Column("category_id", sa.Integer()), sa.Column("category", sa.String(120)), sa.Column("subcategory", sa.String(120)), sa.Column("due_date", sa.Date(), nullable=False), sa.Column("paid_at", sa.Date()), sa.Column("recurrence", sa.String(40), nullable=False, server_default="none"), sa.Column("payment_method", sa.String(60)), sa.Column("account_id", sa.Integer()), sa.Column("card_id", sa.Integer()), sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("tags", sa.String(250)), sa.Column("notes", sa.Text()), sa.Column("attachment_url", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_erp_expenses_user_date_status", "erp_expenses", ["user_id", "due_date", "status"])
    op.create_table("erp_budgets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("month", sa.Integer(), nullable=False), sa.Column("model", sa.String(40), nullable=False, server_default="50_30_20"), sa.Column("monthly_income", sa.Float(), nullable=False, server_default="0"), sa.Column("needs_pct", sa.Float(), nullable=False, server_default="50"), sa.Column("wants_pct", sa.Float(), nullable=False, server_default="30"), sa.Column("investments_pct", sa.Float(), nullable=False, server_default="20"), sa.Column("custom_json", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("user_id", "year", "month", name="uq_erp_budget_user_month"))
    op.create_table("erp_planned_investments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("month", sa.Integer(), nullable=False), sa.Column("planned_amount", sa.Float(), nullable=False, server_default="0"), sa.Column("realized_amount", sa.Float(), nullable=False, server_default="0"), sa.Column("target_asset_class", sa.String(60)), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("erp_alerts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("title", sa.String(160), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("severity", sa.String(20), nullable=False, server_default="info"), sa.Column("source", sa.String(40), nullable=False, server_default="financial_diagnosis"), sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    for table in ["erp_alerts", "erp_planned_investments", "erp_budgets", "erp_expenses", "erp_incomes", "erp_categories", "erp_cards", "erp_accounts"]:
        op.drop_table(table)

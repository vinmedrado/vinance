"""create household financial state v1

Revision ID: 0018_household_state
Revises: 0017_investment_alerts
Create Date: 2026-09-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_household_state"
down_revision = "0017_investment_alerts"
branch_labels = None
depends_on = None


def _create_households() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("household_type", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("household_type IN ('PERSONAL','SHARED')", name="ck_households_type"),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_households_status"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_households_creator_status", "households", ["created_by_user_id", "status"])
    op.create_index(
        "uq_households_personal_creator",
        "households",
        ["created_by_user_id"],
        unique=True,
        postgresql_where=sa.text("household_type = 'PERSONAL' AND status = 'ACTIVE'"),
    )

    op.create_table(
        "household_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="MEMBER"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('OWNER','MEMBER')", name="ck_household_members_role"),
        sa.CheckConstraint("status IN ('ACTIVE','REMOVED')", name="ck_household_members_status"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "user_id", name="uq_household_members_household_user"),
    )
    op.create_index("ix_household_members_user_status", "household_members", ["user_id", "status"])
    op.create_index(
        "uq_household_members_active_default_user",
        "household_members",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND status = 'ACTIVE'"),
    )


def _extend_canonical_cashflow_tables() -> None:
    op.execute("LOCK TABLE users, incomes, expenses IN SHARE ROW EXCLUSIVE MODE")
    op.add_column("incomes", sa.Column("household_id", sa.Integer(), nullable=True))
    op.add_column(
        "incomes",
        sa.Column("ownership_scope", sa.String(length=16), nullable=True, server_default="PERSONAL"),
    )
    op.add_column("expenses", sa.Column("household_id", sa.Integer(), nullable=True))
    op.add_column(
        "expenses",
        sa.Column("ownership_scope", sa.String(length=16), nullable=True, server_default="PERSONAL"),
    )
    op.add_column("expenses", sa.Column("expense_nature", sa.String(length=16), nullable=True))

    op.execute(
        """
        INSERT INTO households (name, household_type, created_by_user_id, status)
        SELECT
            COALESCE(NULLIF(BTRIM(full_name), ''), email) || ' — pessoal',
            'PERSONAL',
            id,
            'ACTIVE'
        FROM users
        """
    )
    op.execute(
        """
        INSERT INTO household_members (household_id, user_id, role, status, is_default)
        SELECT id, created_by_user_id, 'OWNER', 'ACTIVE', true
        FROM households
        WHERE household_type = 'PERSONAL'
        """
    )
    op.execute(
        """
        UPDATE incomes AS item
        SET household_id = household.id, ownership_scope = 'PERSONAL'
        FROM households AS household
        WHERE household.household_type = 'PERSONAL'
          AND household.created_by_user_id = item.user_id
        """
    )
    op.execute(
        """
        UPDATE expenses AS item
        SET household_id = household.id, ownership_scope = 'PERSONAL'
        FROM households AS household
        WHERE household.household_type = 'PERSONAL'
          AND household.created_by_user_id = item.user_id
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM incomes WHERE household_id IS NULL OR ownership_scope IS NULL)
               OR EXISTS (SELECT 1 FROM expenses WHERE household_id IS NULL OR ownership_scope IS NULL) THEN
                RAISE EXCEPTION 'household ownership backfill left orphan financial rows';
            END IF;
        END
        $$
        """
    )

    op.alter_column("incomes", "household_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "incomes",
        "ownership_scope",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default=None,
    )
    op.create_foreign_key(
        "fk_incomes_household_id_households",
        "incomes",
        "households",
        ["household_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_incomes_ownership_scope",
        "incomes",
        "ownership_scope IN ('PERSONAL','HOUSEHOLD')",
    )
    op.create_index("ix_incomes_household_received", "incomes", ["household_id", "received_at"])
    op.create_index(
        "ix_incomes_household_owner",
        "incomes",
        ["household_id", "ownership_scope", "user_id"],
    )

    op.alter_column("expenses", "household_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "expenses",
        "ownership_scope",
        existing_type=sa.String(length=16),
        nullable=False,
        server_default=None,
    )
    op.create_foreign_key(
        "fk_expenses_household_id_households",
        "expenses",
        "households",
        ["household_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_expenses_ownership_scope",
        "expenses",
        "ownership_scope IN ('PERSONAL','HOUSEHOLD')",
    )
    op.create_check_constraint(
        "ck_expenses_nature",
        "expenses",
        "expense_nature IN ('FIXED','VARIABLE')",
    )
    op.create_index("ix_expenses_household_due", "expenses", ["household_id", "due_date"])
    op.create_index(
        "ix_expenses_household_owner",
        "expenses",
        ["household_id", "ownership_scope", "user_id"],
    )


def _create_financial_resources() -> None:
    op.create_table(
        "financial_liabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ownership_scope", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("liability_type", sa.String(length=80), nullable=False),
        sa.Column("current_balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("monthly_payment", sa.Numeric(18, 2), nullable=True),
        sa.Column("annual_interest_rate_pct", sa.Numeric(9, 6), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("balance_as_of", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_financial_liabilities_scope"),
        sa.CheckConstraint("current_balance IS NULL OR current_balance >= 0", name="ck_financial_liabilities_balance"),
        sa.CheckConstraint("monthly_payment IS NULL OR monthly_payment >= 0", name="ck_financial_liabilities_payment"),
        sa.CheckConstraint(
            "annual_interest_rate_pct IS NULL OR annual_interest_rate_pct >= 0",
            name="ck_financial_liabilities_interest",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','PAID','DEFAULTED','CANCELLED')",
            name="ck_financial_liabilities_status",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_liabilities_household_status",
        "financial_liabilities",
        ["household_id", "status"],
    )
    op.create_index(
        "ix_financial_liabilities_owner",
        "financial_liabilities",
        ["household_id", "ownership_scope", "user_id"],
    )

    op.create_table(
        "owned_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ownership_scope", sa.String(length=16), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("asset_catalog_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("current_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("value_as_of", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_owned_assets_scope"),
        sa.CheckConstraint(
            "asset_class IN ('CASH','EMERGENCY_RESERVE','FIXED_INCOME','INVESTMENTS','REAL_ESTATE','VEHICLES','OTHER')",
            name="ck_owned_assets_class",
        ),
        sa.CheckConstraint("current_value IS NULL OR current_value >= 0", name="ck_owned_assets_value"),
        sa.CheckConstraint("name IS NOT NULL OR asset_catalog_id IS NOT NULL", name="ck_owned_assets_identity"),
        sa.CheckConstraint("status IN ('ACTIVE','DISPOSED')", name="ck_owned_assets_status"),
        sa.ForeignKeyConstraint(["asset_catalog_id"], ["asset_catalog.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owned_assets_household_status", "owned_assets", ["household_id", "status"])
    op.create_index(
        "ix_owned_assets_owner",
        "owned_assets",
        ["household_id", "ownership_scope", "user_id"],
    )
    op.create_index("ix_owned_assets_catalog", "owned_assets", ["asset_catalog_id"])

    op.create_table(
        "financial_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ownership_scope", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("current_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_financial_goals_scope"),
        sa.CheckConstraint("target_amount > 0", name="ck_financial_goals_target"),
        sa.CheckConstraint("current_amount IS NULL OR current_amount >= 0", name="ck_financial_goals_current"),
        sa.CheckConstraint("priority IN ('LOW','MEDIUM','HIGH')", name="ck_financial_goals_priority"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','PAUSED','COMPLETED','CANCELLED')",
            name="ck_financial_goals_status",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_goals_household_status", "financial_goals", ["household_id", "status"])
    op.create_index(
        "ix_financial_goals_owner",
        "financial_goals",
        ["household_id", "ownership_scope", "user_id"],
    )
    op.create_index("ix_financial_goals_deadline", "financial_goals", ["household_id", "deadline"])


def _create_immutable_snapshots() -> None:
    op.create_table(
        "financial_state_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("normalized_inputs", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("member_views", sa.JSON(), nullable=False),
        sa.Column("data_quality", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("inconsistencies", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "data_quality IN ('COMPLETE','PARTIAL','INSUFFICIENT','STALE','INCONSISTENT')",
            name="ck_financial_state_snapshots_quality",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_financial_state_snapshots_confidence",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_state_snapshots_household_evaluated",
        "financial_state_snapshots",
        ["household_id", "evaluated_at"],
    )
    op.create_index(
        "uq_financial_state_snapshots_idempotency",
        "financial_state_snapshots",
        ["household_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_financial_state_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'financial_state_snapshots are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_financial_state_snapshots_immutable
        BEFORE UPDATE OR DELETE ON financial_state_snapshots
        FOR EACH ROW EXECUTE FUNCTION reject_financial_state_snapshot_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_financial_state_snapshots_no_truncate
        BEFORE TRUNCATE ON financial_state_snapshots
        FOR EACH STATEMENT EXECUTE FUNCTION reject_financial_state_snapshot_mutation()
        """
    )


def upgrade() -> None:
    _create_households()
    _extend_canonical_cashflow_tables()
    _create_financial_resources()
    _create_immutable_snapshots()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_financial_state_snapshots_no_truncate ON financial_state_snapshots")
    op.execute("DROP TRIGGER IF EXISTS trg_financial_state_snapshots_immutable ON financial_state_snapshots")
    op.execute("DROP FUNCTION IF EXISTS reject_financial_state_snapshot_mutation()")
    op.drop_index("uq_financial_state_snapshots_idempotency", table_name="financial_state_snapshots")
    op.drop_index("ix_financial_state_snapshots_household_evaluated", table_name="financial_state_snapshots")
    op.drop_table("financial_state_snapshots")

    op.drop_index("ix_financial_goals_deadline", table_name="financial_goals")
    op.drop_index("ix_financial_goals_owner", table_name="financial_goals")
    op.drop_index("ix_financial_goals_household_status", table_name="financial_goals")
    op.drop_table("financial_goals")
    op.drop_index("ix_owned_assets_catalog", table_name="owned_assets")
    op.drop_index("ix_owned_assets_owner", table_name="owned_assets")
    op.drop_index("ix_owned_assets_household_status", table_name="owned_assets")
    op.drop_table("owned_assets")
    op.drop_index("ix_financial_liabilities_owner", table_name="financial_liabilities")
    op.drop_index("ix_financial_liabilities_household_status", table_name="financial_liabilities")
    op.drop_table("financial_liabilities")

    op.drop_index("ix_expenses_household_owner", table_name="expenses")
    op.drop_index("ix_expenses_household_due", table_name="expenses")
    op.drop_constraint("ck_expenses_nature", "expenses", type_="check")
    op.drop_constraint("ck_expenses_ownership_scope", "expenses", type_="check")
    op.drop_constraint("fk_expenses_household_id_households", "expenses", type_="foreignkey")
    op.drop_column("expenses", "expense_nature")
    op.drop_column("expenses", "ownership_scope")
    op.drop_column("expenses", "household_id")

    op.drop_index("ix_incomes_household_owner", table_name="incomes")
    op.drop_index("ix_incomes_household_received", table_name="incomes")
    op.drop_constraint("ck_incomes_ownership_scope", "incomes", type_="check")
    op.drop_constraint("fk_incomes_household_id_households", "incomes", type_="foreignkey")
    op.drop_column("incomes", "ownership_scope")
    op.drop_column("incomes", "household_id")

    op.drop_index("uq_household_members_active_default_user", table_name="household_members")
    op.drop_index("ix_household_members_user_status", table_name="household_members")
    op.drop_table("household_members")
    op.drop_index("uq_households_personal_creator", table_name="households")
    op.drop_index("ix_households_creator_status", table_name="households")
    op.drop_table("households")

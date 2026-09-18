"""create immutable capital allocation decisions

Revision ID: 0020_capital_allocation_v1
Revises: 0019_financial_policy_v1
Create Date: 2026-09-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_capital_allocation_v1"
down_revision = "0019_financial_policy_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allocation must reference the exact Policy + State + household chain. This
    # alternate key exists only to support that composite FK; it does not mutate
    # any historical policy row.
    op.create_unique_constraint(
        "uq_financial_policy_decisions_chain",
        "financial_policy_decisions",
        ["id", "financial_state_snapshot_id", "household_id"],
    )
    op.create_table(
        "capital_allocation_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("financial_state_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("financial_policy_decision_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("rules_version", sa.String(length=80), nullable=False),
        sa.Column("allocation_period", sa.String(length=16), nullable=False),
        sa.Column("allocation_status", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("allocatable_capital", sa.Numeric(18, 2), nullable=True),
        sa.Column("allocated_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_capital", sa.Numeric(18, 2), nullable=True),
        sa.Column("investment_bucket_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("ruleset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("decision_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("decision_payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "allocation_period IN ('MONTHLY')",
            name="ck_capital_allocation_decisions_period",
        ),
        sa.CheckConstraint(
            "allocation_status IN ('BLOCKED','CONSTRAINED','ACTIVE','SURPLUS')",
            name="ck_capital_allocation_decisions_status",
        ),
        sa.CheckConstraint(
            "allocatable_capital IS NULL OR allocatable_capital >= 0",
            name="ck_capital_allocation_decisions_allocatable",
        ),
        sa.CheckConstraint(
            "allocated_capital >= 0 AND investment_bucket_amount >= 0",
            name="ck_capital_allocation_decisions_nonnegative",
        ),
        sa.CheckConstraint(
            "investment_bucket_amount <= allocated_capital",
            name="ck_capital_allocation_decisions_investment_bound",
        ),
        sa.CheckConstraint(
            "((allocatable_capital IS NULL AND allocated_capital = 0 "
            "AND remaining_capital IS NULL) OR (allocatable_capital IS NOT NULL "
            "AND remaining_capital IS NOT NULL AND remaining_capital >= 0 "
            "AND allocated_capital <= allocatable_capital "
            "AND allocated_capital + remaining_capital = allocatable_capital))",
            name="ck_capital_allocation_decisions_conservation",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
            ],
            [
                "financial_policy_decisions.id",
                "financial_policy_decisions.financial_state_snapshot_id",
                "financial_policy_decisions.household_id",
            ],
            name="fk_capital_allocation_policy_state_household",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "financial_policy_decision_id",
            "engine_version",
            "rules_version",
            name="uq_capital_allocation_policy_versions",
        ),
    )
    op.create_index(
        "ix_capital_allocation_household_generated",
        "capital_allocation_decisions",
        ["household_id", "generated_at"],
    )
    op.create_index(
        "uq_capital_allocation_idempotency",
        "capital_allocation_decisions",
        ["household_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_capital_allocation_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'capital_allocation_decisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capital_allocation_decisions_immutable
        BEFORE UPDATE OR DELETE ON capital_allocation_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_capital_allocation_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capital_allocation_decisions_no_truncate
        BEFORE TRUNCATE ON capital_allocation_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_capital_allocation_decision_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_capital_allocation_decisions_no_truncate "
        "ON capital_allocation_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_capital_allocation_decisions_immutable "
        "ON capital_allocation_decisions"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_capital_allocation_decision_mutation()")
    op.drop_index(
        "uq_capital_allocation_idempotency",
        table_name="capital_allocation_decisions",
    )
    op.drop_index(
        "ix_capital_allocation_household_generated",
        table_name="capital_allocation_decisions",
    )
    op.drop_table("capital_allocation_decisions")
    op.drop_constraint(
        "uq_financial_policy_decisions_chain",
        "financial_policy_decisions",
        type_="unique",
    )

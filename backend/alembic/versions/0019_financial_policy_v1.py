"""create immutable financial policy decisions

Revision ID: 0019_financial_policy_v1
Revises: 0018_household_state
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_financial_policy_v1"
down_revision = "0018_household_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The composite key makes it impossible to bind a policy row to a State
    # snapshot from another household, even if application validation regresses.
    op.create_unique_constraint(
        "uq_financial_state_snapshots_id_household",
        "financial_state_snapshots",
        ["id", "household_id"],
    )
    op.create_table(
        "financial_policy_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("financial_state_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("rules_version", sa.String(length=80), nullable=False),
        sa.Column("policy_state", sa.String(length=40), nullable=False),
        sa.Column("investment_readiness", sa.String(length=16), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
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
            "policy_state IN ('DATA_BLOCKED','CASHFLOW_RECOVERY','DEBT_PRIORITY',"
            "'EMERGENCY_RESERVE_PRIORITY','GOAL_PRIORITY','BALANCED_BUILD',"
            "'INVESTMENT_READY')",
            name="ck_financial_policy_decisions_state",
        ),
        sa.CheckConstraint(
            "investment_readiness IN ('BLOCKED','LIMITED','READY')",
            name="ck_financial_policy_decisions_readiness",
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
            ["financial_state_snapshot_id", "household_id"],
            ["financial_state_snapshots.id", "financial_state_snapshots.household_id"],
            name="fk_policy_decision_snapshot_household",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "financial_state_snapshot_id",
            "engine_version",
            "rules_version",
            name="uq_policy_decision_snapshot_versions",
        ),
    )
    op.create_index(
        "ix_financial_policy_decisions_household_generated",
        "financial_policy_decisions",
        ["household_id", "generated_at"],
    )
    op.create_index(
        "uq_financial_policy_decisions_idempotency",
        "financial_policy_decisions",
        ["household_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_financial_policy_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'financial_policy_decisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_financial_policy_decisions_immutable
        BEFORE UPDATE OR DELETE ON financial_policy_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_financial_policy_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_financial_policy_decisions_no_truncate
        BEFORE TRUNCATE ON financial_policy_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_financial_policy_decision_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_financial_policy_decisions_no_truncate "
        "ON financial_policy_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_financial_policy_decisions_immutable "
        "ON financial_policy_decisions"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_financial_policy_decision_mutation()")
    op.drop_index(
        "uq_financial_policy_decisions_idempotency",
        table_name="financial_policy_decisions",
    )
    op.drop_index(
        "ix_financial_policy_decisions_household_generated",
        table_name="financial_policy_decisions",
    )
    op.drop_table("financial_policy_decisions")
    op.drop_constraint(
        "uq_financial_state_snapshots_id_household",
        "financial_state_snapshots",
        type_="unique",
    )

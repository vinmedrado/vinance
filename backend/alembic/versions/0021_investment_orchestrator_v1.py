"""create immutable investment orchestration decisions

Revision ID: 0021_investment_orchestrator_v1
Revises: 0020_capital_allocation_v1
Create Date: 2026-09-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_investment_orchestrator_v1"
down_revision = "0020_capital_allocation_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The alternate key binds an orchestration decision to the exact frozen
    # Allocation -> Policy -> State -> household chain and its authorized budget.
    op.create_unique_constraint(
        "uq_capital_allocation_orchestration_chain",
        "capital_allocation_decisions",
        [
            "id",
            "financial_policy_decision_id",
            "financial_state_snapshot_id",
            "household_id",
            "investment_bucket_amount",
        ],
    )
    op.create_table(
        "investment_orchestration_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("financial_state_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("financial_policy_decision_id", sa.Integer(), nullable=False),
        sa.Column("capital_allocation_decision_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("rules_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("investment_budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("suggested_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_investment_cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("speculative_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("allocation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("market_context_fingerprint", sa.String(length=64), nullable=False),
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
            "status IN ('BLOCKED','LIMITED','ACTIVE','NO_SUITABLE_OPPORTUNITY')",
            name="ck_investment_orchestration_status",
        ),
        sa.CheckConstraint(
            "investment_budget >= 0 AND suggested_capital >= 0 "
            "AND remaining_investment_cash >= 0 AND speculative_capital >= 0",
            name="ck_investment_orchestration_nonnegative",
        ),
        sa.CheckConstraint(
            "suggested_capital <= investment_budget "
            "AND suggested_capital + remaining_investment_cash = investment_budget",
            name="ck_investment_orchestration_conservation",
        ),
        sa.CheckConstraint(
            "speculative_capital = 0",
            name="ck_investment_orchestration_no_speculation",
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
                "capital_allocation_decision_id",
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
                "investment_budget",
            ],
            [
                "capital_allocation_decisions.id",
                "capital_allocation_decisions.financial_policy_decision_id",
                "capital_allocation_decisions.financial_state_snapshot_id",
                "capital_allocation_decisions.household_id",
                "capital_allocation_decisions.investment_bucket_amount",
            ],
            name="fk_investment_orchestration_allocation_chain",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "capital_allocation_decision_id",
            "engine_version",
            "rules_version",
            name="uq_investment_orchestration_allocation_versions",
        ),
    )
    op.create_index(
        "ix_investment_orchestration_household_generated",
        "investment_orchestration_decisions",
        ["household_id", "generated_at"],
    )
    op.create_index(
        "uq_investment_orchestration_idempotency",
        "investment_orchestration_decisions",
        ["household_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_investment_orchestration_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'investment_orchestration_decisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_investment_orchestration_decisions_immutable
        BEFORE UPDATE OR DELETE ON investment_orchestration_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_investment_orchestration_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_investment_orchestration_decisions_no_truncate
        BEFORE TRUNCATE ON investment_orchestration_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_investment_orchestration_decision_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_investment_orchestration_decisions_no_truncate "
        "ON investment_orchestration_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_investment_orchestration_decisions_immutable "
        "ON investment_orchestration_decisions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS reject_investment_orchestration_decision_mutation()"
    )
    op.drop_index(
        "uq_investment_orchestration_idempotency",
        table_name="investment_orchestration_decisions",
    )
    op.drop_index(
        "ix_investment_orchestration_household_generated",
        table_name="investment_orchestration_decisions",
    )
    op.drop_table("investment_orchestration_decisions")
    op.drop_constraint(
        "uq_capital_allocation_orchestration_chain",
        "capital_allocation_decisions",
        type_="unique",
    )

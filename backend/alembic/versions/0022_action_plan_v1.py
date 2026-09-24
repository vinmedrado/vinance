"""create immutable action plan decisions

Revision ID: 0022_action_plan_v1
Revises: 0021_investment_orchestrator_v1
Create Date: 2026-09-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_action_plan_v1"
down_revision = "0021_investment_orchestrator_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This alternate key binds A5 to the exact frozen A1 -> A4 chain and to the
    # three monetary values that Action Plan is allowed to represent.
    op.create_unique_constraint(
        "uq_investment_orchestration_action_plan_chain",
        "investment_orchestration_decisions",
        [
            "id",
            "capital_allocation_decision_id",
            "financial_policy_decision_id",
            "financial_state_snapshot_id",
            "household_id",
            "investment_budget",
            "suggested_capital",
            "remaining_investment_cash",
        ],
    )
    op.create_table(
        "action_plan_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("financial_state_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("financial_policy_decision_id", sa.Integer(), nullable=False),
        sa.Column("capital_allocation_decision_id", sa.Integer(), nullable=False),
        sa.Column("investment_orchestration_decision_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("rules_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("authorized_financial_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("investment_budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("suggested_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_investment_cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_financial_actions", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_investment_actions", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_hold_cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("speculative_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("allocation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("orchestration_fingerprint", sa.String(length=64), nullable=False),
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
            "status IN ('BLOCKED','PARTIAL','READY','NO_ACTION_REQUIRED')",
            name="ck_action_plan_status",
        ),
        sa.CheckConstraint("period = 'MONTHLY'", name="ck_action_plan_period"),
        sa.CheckConstraint(
            "authorized_financial_capital >= 0 AND investment_budget >= 0 "
            "AND suggested_capital >= 0 AND total_financial_actions >= 0 "
            "AND total_investment_actions >= 0 AND total_hold_cash >= 0 "
            "AND speculative_capital >= 0",
            name="ck_action_plan_nonnegative",
        ),
        sa.CheckConstraint(
            "total_financial_actions <= authorized_financial_capital",
            name="ck_action_plan_financial_conservation",
        ),
        sa.CheckConstraint(
            "total_investment_actions <= suggested_capital",
            name="ck_action_plan_investment_conservation",
        ),
        sa.CheckConstraint(
            "total_investment_actions + total_hold_cash <= investment_budget",
            name="ck_action_plan_budget_conservation",
        ),
        sa.CheckConstraint(
            "speculative_capital = 0",
            name="ck_action_plan_no_speculation",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            [
                "investment_orchestration_decision_id",
                "capital_allocation_decision_id",
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
                "investment_budget",
                "suggested_capital",
                "remaining_investment_cash",
            ],
            [
                "investment_orchestration_decisions.id",
                "investment_orchestration_decisions.capital_allocation_decision_id",
                "investment_orchestration_decisions.financial_policy_decision_id",
                "investment_orchestration_decisions.financial_state_snapshot_id",
                "investment_orchestration_decisions.household_id",
                "investment_orchestration_decisions.investment_budget",
                "investment_orchestration_decisions.suggested_capital",
                "investment_orchestration_decisions.remaining_investment_cash",
            ],
            name="fk_action_plan_orchestration_chain",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investment_orchestration_decision_id",
            "engine_version",
            "rules_version",
            name="uq_action_plan_orchestration_versions",
        ),
    )
    op.create_index(
        "ix_action_plan_household_generated",
        "action_plan_decisions",
        ["household_id", "generated_at"],
    )
    op.create_index(
        "uq_action_plan_idempotency",
        "action_plan_decisions",
        ["household_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_action_plan_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'action_plan_decisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_action_plan_decisions_immutable
        BEFORE UPDATE OR DELETE ON action_plan_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_action_plan_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_action_plan_decisions_no_truncate
        BEFORE TRUNCATE ON action_plan_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_action_plan_decision_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_action_plan_decisions_no_truncate "
        "ON action_plan_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_action_plan_decisions_immutable "
        "ON action_plan_decisions"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_action_plan_decision_mutation()")
    op.drop_index(
        "uq_action_plan_idempotency", table_name="action_plan_decisions"
    )
    op.drop_index(
        "ix_action_plan_household_generated", table_name="action_plan_decisions"
    )
    op.drop_table("action_plan_decisions")
    op.drop_constraint(
        "uq_investment_orchestration_action_plan_chain",
        "investment_orchestration_decisions",
        type_="unique",
    )

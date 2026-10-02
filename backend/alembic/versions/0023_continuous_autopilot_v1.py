"""continuous autopilot v1 and generic in-app alert delivery

Revision ID: 0023_continuous_autopilot_v1
Revises: 0022_action_plan_v1
Create Date: 2026-09-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0023_continuous_autopilot_v1"
down_revision = "0022_action_plan_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A market-only reevaluation reuses the immutable A1 -> A3 chain,
    # but may legitimately freeze a new A4 context for the same allocation.
    op.drop_constraint(
        "uq_investment_orchestration_allocation_versions",
        "investment_orchestration_decisions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_investment_orchestration_allocation_market",
        "investment_orchestration_decisions",
        [
            "capital_allocation_decision_id",
            "engine_version",
            "rules_version",
            "market_context_fingerprint",
        ],
    )

    # A6 binds both sides of the comparison to the same household in the DB.
    op.create_unique_constraint(
        "uq_action_plan_id_household",
        "action_plan_decisions",
        ["id", "household_id"],
    )

    op.create_table(
        "continuous_autopilot_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("previous_action_plan_id", sa.Integer(), nullable=True),
        sa.Column("current_action_plan_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("rules_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("materiality", sa.String(length=16), nullable=False),
        sa.Column("alert_decision", sa.String(length=32), nullable=False),
        sa.Column("reevaluation_scope", sa.String(length=32), nullable=False),
        sa.Column("change_count", sa.Integer(), nullable=False),
        sa.Column("decision_payload", sa.JSON(), nullable=False),
        sa.Column("previous_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("current_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("ruleset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("decision_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('UP_TO_DATE','REEVALUATION_REQUIRED','EVALUATING',"
            "'CHANGED','UNCHANGED','BLOCKED','FAILED')",
            name="ck_continuous_autopilot_decision_status",
        ),
        sa.CheckConstraint(
            "materiality IN ('NONE','LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_continuous_autopilot_materiality",
        ),
        sa.CheckConstraint(
            "alert_decision IN ('NO_ALERT','INFORMATIONAL','ACTION_RECOMMENDED',"
            "'IMPORTANT','CRITICAL')",
            name="ck_continuous_autopilot_alert_decision",
        ),
        sa.CheckConstraint(
            "reevaluation_scope IN ('NONE','FULL_CHAIN','INVESTMENT_CHAIN')",
            name="ck_continuous_autopilot_scope",
        ),
        sa.CheckConstraint(
            "change_count >= 0", name="ck_continuous_autopilot_change_count"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["previous_action_plan_id", "household_id"],
            ["action_plan_decisions.id", "action_plan_decisions.household_id"],
            name="fk_continuous_autopilot_previous_plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["current_action_plan_id", "household_id"],
            ["action_plan_decisions.id", "action_plan_decisions.household_id"],
            name="fk_continuous_autopilot_current_plan",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "decision_fingerprint",
            name="uq_continuous_autopilot_household_fingerprint",
        ),
        sa.UniqueConstraint(
            "id",
            "household_id",
            name="uq_continuous_autopilot_id_household",
        ),
        sa.UniqueConstraint(
            "id",
            "household_id",
            "current_action_plan_id",
            name="uq_continuous_autopilot_id_household_plan",
        ),
    )
    op.create_index(
        "ix_continuous_autopilot_household_generated",
        "continuous_autopilot_decisions",
        ["household_id", "generated_at"],
    )
    op.create_index(
        "uq_continuous_autopilot_dedupe",
        "continuous_autopilot_decisions",
        ["household_id", "dedupe_key"],
        unique=True,
    )

    # A decision can be returned for more than one logically equivalent request.
    # Keep every Idempotency-Key bound to the exact frozen response it received.
    op.create_table(
        "continuous_autopilot_requests",
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("continuous_decision_id", sa.Integer(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["continuous_decision_id", "household_id"],
            [
                "continuous_autopilot_decisions.id",
                "continuous_autopilot_decisions.household_id",
            ],
            name="fk_continuous_autopilot_request_decision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("household_id", "idempotency_key"),
    )
    op.create_index(
        "ix_continuous_autopilot_requests_decision",
        "continuous_autopilot_requests",
        ["continuous_decision_id", "household_id"],
    )

    op.create_table(
        "continuous_autopilot_states",
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pending_categories", sa.JSON(), nullable=False),
        sa.Column("last_action_plan_id", sa.Integer(), nullable=True),
        sa.Column("last_continuous_decision_id", sa.Integer(), nullable=True),
        sa.Column("dirty_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("active_alert_key", sa.String(length=64), nullable=True),
        sa.Column("alert_episode", sa.Integer(), server_default="0", nullable=False),
        sa.Column("evaluation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alert_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("no_change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('UP_TO_DATE','REEVALUATION_REQUIRED','EVALUATING',"
            "'CHANGED','UNCHANGED','BLOCKED','FAILED')",
            name="ck_continuous_autopilot_state_status",
        ),
        sa.CheckConstraint(
            "evaluation_count >= 0 AND change_count >= 0 AND alert_count >= 0 "
            "AND no_change_count >= 0 AND failure_count >= 0 "
            "AND alert_episode >= 0",
            name="ck_continuous_autopilot_state_counters",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "(last_action_plan_id IS NULL) = "
            "(last_continuous_decision_id IS NULL)",
            name="ck_continuous_autopilot_state_pointer_pair",
        ),
        sa.ForeignKeyConstraint(
            [
                "last_continuous_decision_id",
                "household_id",
                "last_action_plan_id",
            ],
            [
                "continuous_autopilot_decisions.id",
                "continuous_autopilot_decisions.household_id",
                "continuous_autopilot_decisions.current_action_plan_id",
            ],
            name="fk_continuous_autopilot_state_chain",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("household_id"),
    )
    op.create_index(
        "ix_continuous_autopilot_states_status_dirty",
        "continuous_autopilot_states",
        ["status", "dirty_since"],
    )
    op.create_index(
        "ix_continuous_autopilot_states_last_evaluated",
        "continuous_autopilot_states",
        ["last_evaluated_at"],
    )
    op.execute(
        """
        INSERT INTO continuous_autopilot_states
            (household_id, status, pending_categories, dirty_since)
        SELECT id, 'REEVALUATION_REQUIRED', '[\"HOUSEHOLD\"]'::json, now()
        FROM households
        ON CONFLICT (household_id) DO NOTHING
        """
    )

    # Reuse the existing IN_APP inbox. Legacy investment alerts are backfilled
    # as INVESTMENT; A6 alerts use the same read-state and dedupe machinery.
    op.drop_constraint("ck_investment_alerts_type", "investment_alerts", type_="check")
    op.drop_constraint("ck_investment_alerts_severity", "investment_alerts", type_="check")
    op.alter_column("investment_alerts", "decision_id", nullable=True)
    op.alter_column("investment_alerts", "asset", nullable=True)
    op.add_column(
        "investment_alerts",
        sa.Column(
            "source_domain",
            sa.String(length=32),
            server_default="INVESTMENT",
            nullable=False,
        ),
    )
    op.add_column(
        "investment_alerts", sa.Column("source_reference", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "investment_alerts", sa.Column("household_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "investment_alerts",
        sa.Column("continuous_decision_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investment_alerts", sa.Column("ownership_scope", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "investment_alerts", sa.Column("owner_user_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_investment_alerts_household",
        "investment_alerts",
        "households",
        ["household_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_investment_alerts_continuous_household",
        "investment_alerts",
        "continuous_autopilot_decisions",
        ["continuous_decision_id", "household_id"],
        ["id", "household_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_investment_alerts_owner_user",
        "investment_alerts",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_investment_alerts_recipient_membership",
        "investment_alerts",
        "household_members",
        ["household_id", "user_id"],
        ["household_id", "user_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_investment_alerts_owner_membership",
        "investment_alerts",
        "household_members",
        ["household_id", "owner_user_id"],
        ["household_id", "user_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_investment_alerts_type",
        "investment_alerts",
        "alert_type IN ('NEW_OPPORTUNITY','ACTION_CHANGE','SCORE_CHANGE',"
        "'CONFIDENCE_CHANGE','RISK_CHANGE','CONTINUOUS_AUTOPILOT_CHANGE')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_severity",
        "investment_alerts",
        "severity IN ('INFO','MEDIUM','HIGH','CRITICAL')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_source_domain",
        "investment_alerts",
        "source_domain IN ('INVESTMENT','CONTINUOUS_AUTOPILOT')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_source_contract",
        "investment_alerts",
        "(source_domain = 'INVESTMENT' AND decision_id IS NOT NULL "
        "AND asset IS NOT NULL AND continuous_decision_id IS NULL "
        "AND household_id IS NULL AND ownership_scope IS NULL "
        "AND owner_user_id IS NULL "
        "AND alert_type <> 'CONTINUOUS_AUTOPILOT_CHANGE') OR "
        "(source_domain = 'CONTINUOUS_AUTOPILOT' AND decision_id IS NULL "
        "AND asset IS NULL AND continuous_decision_id IS NOT NULL "
        "AND household_id IS NOT NULL AND subscription_id IS NULL "
        "AND ownership_scope IS NOT NULL AND source_reference IS NOT NULL "
        "AND alert_type = 'CONTINUOUS_AUTOPILOT_CHANGE')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_ownership_scope",
        "investment_alerts",
        "ownership_scope IS NULL OR ownership_scope IN ('PERSONAL','HOUSEHOLD')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_personal_owner",
        "investment_alerts",
        "ownership_scope <> 'PERSONAL' OR owner_user_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_investment_alerts_household_owner",
        "investment_alerts",
        "ownership_scope <> 'HOUSEHOLD' OR owner_user_id IS NULL",
    )
    op.create_index(
        "ix_investment_alerts_household_created",
        "investment_alerts",
        ["household_id", "created_at"],
    )
    op.create_index(
        "ix_investment_alerts_continuous_decision",
        "investment_alerts",
        ["continuous_decision_id", "user_id"],
    )

    op.execute(
        """
        CREATE FUNCTION reject_continuous_autopilot_decision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'continuous_autopilot_decisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_continuous_autopilot_decisions_immutable
        BEFORE UPDATE OR DELETE ON continuous_autopilot_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_continuous_autopilot_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_continuous_autopilot_decisions_no_truncate
        BEFORE TRUNCATE ON continuous_autopilot_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_continuous_autopilot_decision_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_continuous_autopilot_request_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'continuous_autopilot_requests are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_continuous_autopilot_requests_immutable
        BEFORE UPDATE OR DELETE ON continuous_autopilot_requests
        FOR EACH ROW EXECUTE FUNCTION reject_continuous_autopilot_request_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_continuous_autopilot_requests_no_truncate
        BEFORE TRUNCATE ON continuous_autopilot_requests
        FOR EACH STATEMENT EXECUTE FUNCTION reject_continuous_autopilot_request_mutation()
        """
    )


def downgrade() -> None:
    # Capture exact A4/A5 rows while the immutable A6 ledger still exists.
    # Public Idempotency-Key values are not provenance and must never decide
    # which immutable decisions are deleted.
    op.execute(
        """
        CREATE TEMPORARY TABLE a6_downgrade_partial_chain_ids
        ON COMMIT DROP
        AS
        SELECT DISTINCT
            current_plan.id AS action_plan_id,
            current_orchestration.id AS orchestration_id
        FROM continuous_autopilot_decisions AS continuous
        JOIN action_plan_decisions AS current_plan
          ON current_plan.id = continuous.current_action_plan_id
         AND current_plan.household_id = continuous.household_id
        JOIN action_plan_decisions AS previous_plan
          ON previous_plan.id = continuous.previous_action_plan_id
         AND previous_plan.household_id = continuous.household_id
        JOIN investment_orchestration_decisions AS current_orchestration
          ON current_orchestration.id =
             current_plan.investment_orchestration_decision_id
        JOIN investment_orchestration_decisions AS previous_orchestration
          ON previous_orchestration.id =
             previous_plan.investment_orchestration_decision_id
        WHERE continuous.reevaluation_scope = 'INVESTMENT_CHAIN'
          AND current_orchestration.id > previous_orchestration.id
          AND current_orchestration.capital_allocation_decision_id =
              previous_orchestration.capital_allocation_decision_id
          AND current_orchestration.engine_version =
              previous_orchestration.engine_version
          AND current_orchestration.rules_version =
              previous_orchestration.rules_version
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_continuous_autopilot_requests_no_truncate "
        "ON continuous_autopilot_requests"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_continuous_autopilot_requests_immutable "
        "ON continuous_autopilot_requests"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_continuous_autopilot_request_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_continuous_autopilot_decisions_no_truncate "
        "ON continuous_autopilot_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_continuous_autopilot_decisions_immutable "
        "ON continuous_autopilot_decisions"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_continuous_autopilot_decision_mutation()")

    # Old F37 schema cannot represent A6 deliveries.
    op.execute(
        "DELETE FROM investment_alerts WHERE source_domain = 'CONTINUOUS_AUTOPILOT'"
    )
    op.drop_index(
        "ix_investment_alerts_continuous_decision", table_name="investment_alerts"
    )
    op.drop_index(
        "ix_investment_alerts_household_created", table_name="investment_alerts"
    )
    op.drop_constraint(
        "ck_investment_alerts_household_owner", "investment_alerts", type_="check"
    )
    op.drop_constraint(
        "ck_investment_alerts_personal_owner", "investment_alerts", type_="check"
    )
    op.drop_constraint(
        "ck_investment_alerts_ownership_scope", "investment_alerts", type_="check"
    )
    op.drop_constraint(
        "ck_investment_alerts_source_contract", "investment_alerts", type_="check"
    )
    op.drop_constraint(
        "ck_investment_alerts_source_domain", "investment_alerts", type_="check"
    )
    op.drop_constraint("ck_investment_alerts_type", "investment_alerts", type_="check")
    op.drop_constraint("ck_investment_alerts_severity", "investment_alerts", type_="check")
    op.drop_constraint(
        "fk_investment_alerts_owner_membership",
        "investment_alerts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_investment_alerts_recipient_membership",
        "investment_alerts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_investment_alerts_owner_user", "investment_alerts", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_investment_alerts_continuous_household",
        "investment_alerts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_investment_alerts_household", "investment_alerts", type_="foreignkey"
    )
    op.drop_column("investment_alerts", "owner_user_id")
    op.drop_column("investment_alerts", "ownership_scope")
    op.drop_column("investment_alerts", "continuous_decision_id")
    op.drop_column("investment_alerts", "household_id")
    op.drop_column("investment_alerts", "source_reference")
    op.drop_column("investment_alerts", "source_domain")
    op.alter_column("investment_alerts", "asset", nullable=False)
    op.alter_column("investment_alerts", "decision_id", nullable=False)
    op.create_check_constraint(
        "ck_investment_alerts_type",
        "investment_alerts",
        "alert_type IN ('NEW_OPPORTUNITY','ACTION_CHANGE','SCORE_CHANGE',"
        "'CONFIDENCE_CHANGE','RISK_CHANGE')",
    )
    op.create_check_constraint(
        "ck_investment_alerts_severity",
        "investment_alerts",
        "severity IN ('INFO','MEDIUM','HIGH')",
    )

    op.drop_index(
        "ix_continuous_autopilot_states_last_evaluated",
        table_name="continuous_autopilot_states",
    )
    op.drop_index(
        "ix_continuous_autopilot_states_status_dirty",
        table_name="continuous_autopilot_states",
    )
    op.drop_table("continuous_autopilot_states")
    op.drop_index(
        "ix_continuous_autopilot_requests_decision",
        table_name="continuous_autopilot_requests",
    )
    op.drop_table("continuous_autopilot_requests")
    op.drop_index(
        "uq_continuous_autopilot_dedupe",
        table_name="continuous_autopilot_decisions",
    )
    op.drop_index(
        "ix_continuous_autopilot_household_generated",
        table_name="continuous_autopilot_decisions",
    )
    op.drop_table("continuous_autopilot_decisions")

    # Remove only the exact A5/A4 rows proven by the A6 ledger to belong to a
    # partial investment-chain transition. Delete A5 before its referenced A4.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_action_plan_decisions_immutable "
        "ON action_plan_decisions"
    )
    op.execute(
        """
        DELETE FROM action_plan_decisions AS action_plan
        USING a6_downgrade_partial_chain_ids AS doomed
        WHERE action_plan.id = doomed.action_plan_id
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
        "DROP TRIGGER IF EXISTS trg_investment_orchestration_decisions_immutable "
        "ON investment_orchestration_decisions"
    )
    op.execute(
        """
        DELETE FROM investment_orchestration_decisions AS orchestration
        USING a6_downgrade_partial_chain_ids AS doomed
        WHERE orchestration.id = doomed.orchestration_id
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_investment_orchestration_decisions_immutable
        BEFORE UPDATE OR DELETE ON investment_orchestration_decisions
        FOR EACH ROW EXECUTE FUNCTION reject_investment_orchestration_decision_mutation()
        """
    )
    op.drop_constraint(
        "uq_investment_orchestration_allocation_market",
        "investment_orchestration_decisions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_investment_orchestration_allocation_versions",
        "investment_orchestration_decisions",
        ["capital_allocation_decision_id", "engine_version", "rules_version"],
    )
    op.drop_constraint(
        "uq_action_plan_id_household", "action_plan_decisions", type_="unique"
    )

from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint

from backend.app.action_plan.models import ActionPlanDecision
from backend.app.continuous_autopilot.models import (
    ContinuousAutopilotDecision,
    ContinuousAutopilotRequest,
    ContinuousAutopilotState,
)
from backend.app.investment_alerts.models import InvestmentAlert
from backend.app.investment_orchestrator.models import (
    InvestmentOrchestrationDecision,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/alembic/versions/0023_continuous_autopilot_v1.py"


def test_continuous_models_use_canonical_metadata_and_household_chain() -> None:
    assert ContinuousAutopilotDecision.metadata is ActionPlanDecision.metadata
    assert ContinuousAutopilotState.metadata is ActionPlanDecision.metadata
    assert ContinuousAutopilotDecision.__table__.name == "continuous_autopilot_decisions"
    assert ContinuousAutopilotRequest.__table__.name == "continuous_autopilot_requests"
    assert ContinuousAutopilotState.__table__.name == "continuous_autopilot_states"
    assert ContinuousAutopilotRequest.__table__.c.request_fingerprint.nullable is False

    constraints = ContinuousAutopilotDecision.__table__.constraints
    names = {item.name for item in constraints}
    assert "fk_continuous_autopilot_previous_plan" in names
    assert "fk_continuous_autopilot_current_plan" in names
    assert "uq_continuous_autopilot_household_fingerprint" in names
    for name in (
        "ck_continuous_autopilot_decision_status",
        "ck_continuous_autopilot_materiality",
        "ck_continuous_autopilot_alert_decision",
        "ck_continuous_autopilot_scope",
    ):
        assert name in names

    current_fk = next(
        item
        for item in constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_continuous_autopilot_current_plan"
    )
    assert [element.target_fullname for element in current_fk.elements] == [
        "action_plan_decisions.id",
        "action_plan_decisions.household_id",
    ]
    request_fk = next(
        item
        for item in ContinuousAutopilotRequest.__table__.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_continuous_autopilot_request_decision"
    )
    assert [element.target_fullname for element in request_fk.elements] == [
        "continuous_autopilot_decisions.id",
        "continuous_autopilot_decisions.household_id",
    ]


def test_continuous_uniqueness_indexes_and_mutable_state_are_explicit() -> None:
    action_constraints = ActionPlanDecision.__table__.constraints
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_action_plan_id_household"
        for item in action_constraints
    )
    decision_indexes = {
        item.name: item for item in ContinuousAutopilotDecision.__table__.indexes
    }
    assert decision_indexes["uq_continuous_autopilot_dedupe"].unique is True
    assert {
        column.name for column in ContinuousAutopilotRequest.__table__.primary_key.columns
    } == {"household_id", "idempotency_key"}
    state_checks = {
        item.name
        for item in ContinuousAutopilotState.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "ck_continuous_autopilot_state_status" in state_checks
    assert "ck_continuous_autopilot_state_counters" in state_checks
    assert "ck_continuous_autopilot_state_pointer_pair" in state_checks
    state_chain = next(
        item
        for item in ContinuousAutopilotState.__table__.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_continuous_autopilot_state_chain"
    )
    assert [element.target_fullname for element in state_chain.elements] == [
        "continuous_autopilot_decisions.id",
        "continuous_autopilot_decisions.household_id",
        "continuous_autopilot_decisions.current_action_plan_id",
    ]

    orchestration_constraints = InvestmentOrchestrationDecision.__table__.constraints
    partial_unique = next(
        item
        for item in orchestration_constraints
        if isinstance(item, UniqueConstraint)
        and item.name == "uq_investment_orchestration_allocation_market"
    )
    assert [column.name for column in partial_unique.columns] == [
        "capital_allocation_decision_id",
        "engine_version",
        "rules_version",
        "market_context_fingerprint",
    ]


def test_existing_alert_inbox_is_extended_not_duplicated() -> None:
    table = InvestmentAlert.__table__
    assert table.name == "investment_alerts"
    assert {
        "source_domain",
        "household_id",
        "continuous_decision_id",
        "ownership_scope",
        "owner_user_id",
    }.issubset(table.columns.keys())
    checks = {
        item.name
        for item in table.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "ck_investment_alerts_source_contract" in checks
    assert "ck_investment_alerts_personal_owner" in checks
    assert "ck_investment_alerts_household_owner" in checks
    foreign_keys = {
        item.name: item
        for item in table.constraints
        if isinstance(item, ForeignKeyConstraint)
    }
    assert "fk_investment_alerts_continuous_household" in foreign_keys
    assert "fk_investment_alerts_recipient_membership" in foreign_keys
    assert "fk_investment_alerts_owner_membership" in foreign_keys


def test_manual_migration_is_linear_immutable_and_preserves_trading_schema() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0023_continuous_autopilot_v1"' in source
    assert 'down_revision = "0022_action_plan_v1"' in source
    assert "continuous_autopilot_decisions" in source
    assert "continuous_autopilot_requests" in source
    assert "continuous_autopilot_states" in source
    assert "request_fingerprint" in source
    assert "reject_continuous_autopilot_decision_mutation" in source
    assert "reject_continuous_autopilot_request_mutation" in source
    assert "investment_alerts" in source
    assert "uq_investment_orchestration_allocation_market" in source
    assert "autopilot_change_events" not in source
    for trading_table in (
        "trading_feature_artifacts",
        "trading_model_artifacts",
        "trading_predictions",
        "paper_orders",
        "paper_positions",
        "backtest_runs",
    ):
        assert trading_table not in source


def test_migration_does_not_use_autogenerate_or_create_all() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()
    assert "autogenerate" not in source
    assert "create_all" not in source


def test_downgrade_cleanup_uses_a6_edges_not_public_idempotency_keys() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source.split("def downgrade() -> None:", maxsplit=1)[1]

    # Prefixes semelhantes continuam validos nos endpoints publicos A4/A5.
    # Logo, nenhum Idempotency-Key pode participar do conjunto de exclusao.
    assert "idempotency_key LIKE" not in downgrade
    assert "WHERE idempotency_key" not in downgrade

    # A exclusao e limitada aos IDs A4/A5 alcancados por uma aresta A6
    # INVESTMENT_CHAIN que criou um A4 posterior e conflitante com 0022.
    assert "CREATE TEMPORARY TABLE a6_downgrade_partial_chain_ids" in downgrade
    assert "current_plan.id AS action_plan_id" in downgrade
    assert "current_orchestration.id AS orchestration_id" in downgrade
    assert "FROM continuous_autopilot_decisions AS continuous" in downgrade
    assert "continuous.reevaluation_scope = 'INVESTMENT_CHAIN'" in downgrade
    assert "current_orchestration.id > previous_orchestration.id" in downgrade
    assert "WHERE action_plan.id = doomed.action_plan_id" in downgrade
    assert "WHERE orchestration.id = doomed.orchestration_id" in downgrade
    assert downgrade.count(
        "USING a6_downgrade_partial_chain_ids AS doomed"
    ) == 2

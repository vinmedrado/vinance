from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import Request, Response
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint

from backend.app.action_plan.models import ActionPlanDecision
from backend.app.action_plan.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.investment_orchestrator.models import InvestmentOrchestrationDecision
from backend.app.main import security_headers


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/alembic/versions/0022_action_plan_v1.py"


def test_action_plan_model_uses_canonical_metadata_and_immutable_chain() -> None:
    table = ActionPlanDecision.__table__
    assert table.name == "action_plan_decisions"
    assert ENGINE_VERSION == "action-plan-v1"
    assert RULES_VERSION == "action-plan-rules-v1"

    checks = {
        item.name: str(item.sqltext)
        for item in table.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "ck_action_plan_status" in checks
    assert "ck_action_plan_financial_conservation" in checks
    assert "ck_action_plan_investment_conservation" in checks
    assert "ck_action_plan_budget_conservation" in checks
    assert checks["ck_action_plan_no_speculation"] == "speculative_capital = 0"

    chain = next(
        item
        for item in table.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_action_plan_orchestration_chain"
    )
    assert [element.target_fullname for element in chain.elements] == [
        "investment_orchestration_decisions.id",
        "investment_orchestration_decisions.capital_allocation_decision_id",
        "investment_orchestration_decisions.financial_policy_decision_id",
        "investment_orchestration_decisions.financial_state_snapshot_id",
        "investment_orchestration_decisions.household_id",
        "investment_orchestration_decisions.investment_budget",
        "investment_orchestration_decisions.suggested_capital",
        "investment_orchestration_decisions.remaining_investment_cash",
    ]


def test_action_plan_uniqueness_and_indexes_are_household_scoped() -> None:
    constraints = ActionPlanDecision.__table__.constraints
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_action_plan_orchestration_versions"
        for item in constraints
    )
    indexes = {
        item.name: item
        for item in ActionPlanDecision.__table__.indexes
        if isinstance(item, Index)
    }
    assert indexes["uq_action_plan_idempotency"].unique is True
    assert [column.name for column in indexes["uq_action_plan_idempotency"].columns] == [
        "household_id",
        "idempotency_key",
    ]
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_investment_orchestration_action_plan_chain"
        for item in InvestmentOrchestrationDecision.__table__.constraints
    )


def test_action_plan_router_is_registered_once() -> None:
    api_source = (ROOT / "backend/app/api/v1/router.py").read_text(encoding="utf-8")
    router_source = (ROOT / "backend/app/action_plan/router.py").read_text(
        encoding="utf-8"
    )
    assert api_source.count("api_router.include_router(action_plan_router)") == 1
    for suffix in (
        '"/households/{household_id}/action-plan"',
        '"/households/{household_id}/action-plan/from-orchestration/{orchestration_id}"',
        '"/households/{household_id}/action-plan/decisions"',
        '"/households/{household_id}/action-plan/history"',
        '"/households/{household_id}/action-plan/history/{action_plan_id}"',
    ):
        assert router_source.count(suffix) == 1


@pytest.mark.asyncio
async def test_action_plan_security_headers_cover_pre_router_auth_errors() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/financial/households/10/action-plan",
            "root_path": "",
            "query_string": b"",
            "headers": [],
            "client": ("test", 123),
            "server": ("test", 80),
        }
    )

    async def unauthorized(_: Request) -> Response:
        return Response(status_code=401)

    response = await security_headers(request, unauthorized)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"


def test_manual_migration_is_reversible_immutable_and_does_not_touch_trading() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0022_action_plan_v1"' in source
    assert 'down_revision = "0021_investment_orchestrator_v1"' in source
    assert 'op.create_table(\n        "action_plan_decisions"' in source
    assert 'op.drop_table("action_plan_decisions")' in source
    assert "BEFORE UPDATE OR DELETE ON action_plan_decisions" in source
    assert "BEFORE TRUNCATE ON action_plan_decisions" in source
    for external in (
        "acoes_ml_features",
        "fii_ml_features",
        "etf_ml_features",
        "bdr_ml_features",
        "cripto_ml_features",
        "trading_feature_store_v2",
    ):
        assert external not in source

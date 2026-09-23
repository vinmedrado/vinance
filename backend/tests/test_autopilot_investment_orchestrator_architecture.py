from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, UniqueConstraint

from backend.alembic.schema_ownership import TRADING_EXTERNAL_TABLES
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.core.database import Base
from backend.app.investment_orchestrator.models import InvestmentOrchestrationDecision
from backend.app.investment_orchestrator.rules import (
    ENGINE_VERSION,
    MONEY_QUANTUM,
    RULES,
    RULES_VERSION,
    SUPPORTED_MARKETS,
)
from backend.app.investment_orchestrator.schemas import InvestmentOrchestrationRead
from backend.tests.test_autopilot_investment_orchestrator_service import _orchestration


ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "backend" / "app" / "investment_orchestrator"
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "0021_investment_orchestrator_v1.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_orchestrator_uses_single_canonical_base() -> None:
    assert InvestmentOrchestrationDecision.metadata is Base.metadata
    assert CapitalAllocationDecision.metadata is Base.metadata
    assert InvestmentOrchestrationDecision.__table__.name == "investment_orchestration_decisions"


def test_ruleset_is_versioned_conservative_and_has_no_fixed_class_weights() -> None:
    assert ENGINE_VERSION == "investment-orchestrator-v1"
    assert RULES_VERSION == "investment-orchestrator-rules-v1"
    assert MONEY_QUANTUM == Decimal("0.01")
    assert RULES.rounding_mode == "ROUND_DOWN"
    assert RULES.speculative_capital == 0
    assert set(SUPPORTED_MARKETS) == {"ACOES", "FII", "ETF", "BDR"}
    source = _text(DOMAIN / "rules.py") + _text(DOMAIN / "engine.py")
    assert "PROFILE_DIVERSIFIED_ALLOCATIONS" not in source
    assert "get_diversified_allocation" not in source


def test_public_schema_rejects_nonzero_speculative_capital() -> None:
    payload = _orchestration()
    payload["speculative_capital"] = Decimal("0.01")
    with pytest.raises(ValidationError):
        InvestmentOrchestrationRead.model_validate(payload)


def test_model_indexes_immutable_audit_and_money_contract() -> None:
    table = InvestmentOrchestrationDecision.__table__
    for name in (
        "financial_state_snapshot_id",
        "financial_policy_decision_id",
        "capital_allocation_decision_id",
        "decision_payload",
    ):
        assert table.columns[name].nullable is False
    assert isinstance(table.columns["investment_budget"].type, Numeric)
    assert table.columns["investment_budget"].type.precision == 18
    assert table.columns["investment_budget"].type.scale == 2
    assert {index.name for index in table.indexes} == {
        "ix_investment_orchestration_household_generated",
        "uq_investment_orchestration_idempotency",
    }


def test_composite_fk_enforces_exact_a1_to_a4_chain_and_budget() -> None:
    constraint = next(
        item
        for item in InvestmentOrchestrationDecision.__table__.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_investment_orchestration_allocation_chain"
    )
    assert list(constraint.column_keys) == [
        "capital_allocation_decision_id",
        "financial_policy_decision_id",
        "financial_state_snapshot_id",
        "household_id",
        "investment_budget",
    ]
    assert [item.target_fullname for item in constraint.elements] == [
        "capital_allocation_decisions.id",
        "capital_allocation_decisions.financial_policy_decision_id",
        "capital_allocation_decisions.financial_state_snapshot_id",
        "capital_allocation_decisions.household_id",
        "capital_allocation_decisions.investment_bucket_amount",
    ]
    assert constraint.ondelete == "RESTRICT"
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_capital_allocation_orchestration_chain"
        for item in CapitalAllocationDecision.__table__.constraints
    )


def test_database_constraints_enforce_conservation_and_no_speculation() -> None:
    checks = {
        item.name: str(item.sqltext)
        for item in InvestmentOrchestrationDecision.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "suggested_capital + remaining_investment_cash = investment_budget" in checks[
        "ck_investment_orchestration_conservation"
    ]
    assert checks["ck_investment_orchestration_no_speculation"] == "speculative_capital = 0"


def test_manual_migration_is_linear_reversible_immutable_and_trading_safe() -> None:
    source = _text(MIGRATION)
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "0021_investment_orchestrator_v1",
        "down_revision": "0020_capital_allocation_v1",
    }
    assert 'op.create_table(\n        "investment_orchestration_decisions"' in source
    assert 'op.drop_table("investment_orchestration_decisions")' in source
    assert "BEFORE UPDATE OR DELETE ON investment_orchestration_decisions" in source
    assert "BEFORE TRUNCATE ON investment_orchestration_decisions" in source
    assert "autogenerate" not in source.lower()
    lower = source.lower()
    assert all(table not in lower for table in TRADING_EXTERNAL_TABLES)


def test_metadata_router_and_api_registration_are_explicit() -> None:
    env = _text(ROOT / "backend" / "alembic" / "env.py")
    api = _text(ROOT / "backend" / "app" / "api" / "v1" / "router.py")
    router = _text(DOMAIN / "router.py")
    assert "InvestmentOrchestrationDecision" in env
    assert "investment_orchestrator_router" in api
    assert router.count("@router.get(") == 4
    assert router.count("@router.post(") == 1
    assert "@router.put(" not in router
    assert "@router.patch(" not in router
    assert "@router.delete(" not in router
    assert "get_current_user" in router
    assert 'response.headers["Cache-Control"] = "private, no-store"' in router


def test_domain_has_no_legacy_database_or_trading_dispatch_dependency() -> None:
    sources = "\n".join(_text(path) for path in DOMAIN.glob("*.py"))
    lowered = sources.lower()
    for forbidden in (
        "db.database",
        "create_all(",
        "backend.trading",
        "paper_order",
        "prediction_engine",
    ):
        assert forbidden not in lowered
    assert '"trading_dispatch": false' in lowered

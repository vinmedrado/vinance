from __future__ import annotations

import ast
from pathlib import Path
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, UniqueConstraint

from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.capital_allocation.rules import ENGINE_VERSION, RULE_CATALOG, RULES, RULES_VERSION
from backend.app.capital_allocation.schemas import AllocationBucketTotals
from backend.alembic.schema_ownership import TRADING_EXTERNAL_TABLES
from backend.app.core.database import Base
from backend.app.financial_policy.models import FinancialPolicyDecision


ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "backend" / "app" / "capital_allocation"
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "0020_capital_allocation_v1.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_allocation_uses_the_single_canonical_base() -> None:
    assert CapitalAllocationDecision.metadata is Base.metadata
    assert FinancialPolicyDecision.metadata is Base.metadata
    assert CapitalAllocationDecision.__table__.name == "capital_allocation_decisions"


def test_ruleset_versions_rounding_and_speculative_default_are_frozen() -> None:
    assert ENGINE_VERSION == "capital-allocation-v1"
    assert RULES_VERSION == "capital-allocation-rules-v1"
    assert RULES.allocation_period == "MONTHLY"
    assert RULES.money_quantum == Decimal("0.01")
    assert RULES.rounding_mode == "ROUND_DOWN"
    assert RULES.speculative_capital_amount == Decimal("0.00")
    assert set(RULE_CATALOG) == {
        "CAV1-DATA-001",
        "CAV1-DATA-002",
        "CAV1-DATA-003",
        "CAV1-DATA-004",
        "CAV1-CAPITAL-001",
        "CAV1-CAPITAL-002",
        "CAV1-ORDER-001",
        "CAV1-CASH-001",
        "CAV1-DEBT-001",
        "CAV1-RESERVE-001",
        "CAV1-GOAL-001",
        "CAV1-OWN-001",
        "CAV1-INVEST-001",
        "CAV1-PROTECT-001",
        "CAV1-CONSERVE-001",
        "CAV1-ROUND-001",
    }


def test_public_schema_rejects_nonzero_speculative_capital() -> None:
    with pytest.raises(ValidationError):
        AllocationBucketTotals(
            protected_capital=0,
            goal_capital=0,
            investment_capital=0,
            speculative_capital=Decimal("0.01"),
        )


def test_model_indexes_the_immutable_audit_contract() -> None:
    table = CapitalAllocationDecision.__table__
    assert table.columns["financial_state_snapshot_id"].nullable is False
    assert table.columns["financial_policy_decision_id"].nullable is False
    assert table.columns["decision_payload"].nullable is False
    assert table.columns["idempotency_key"].nullable is True
    assert table.columns["allocatable_capital"].nullable is True
    assert table.columns["remaining_capital"].nullable is True
    assert isinstance(table.columns["allocated_capital"].type, Numeric)
    assert table.columns["allocated_capital"].type.precision == 18
    assert table.columns["allocated_capital"].type.scale == 2
    assert {index.name for index in table.indexes} == {
        "ix_capital_allocation_household_generated",
        "uq_capital_allocation_idempotency",
    }


def test_composite_fk_enforces_exact_state_policy_household_chain() -> None:
    table = CapitalAllocationDecision.__table__
    constraint = next(
        item
        for item in table.constraints
        if isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_capital_allocation_policy_state_household"
    )
    assert list(constraint.column_keys) == [
        "financial_policy_decision_id",
        "financial_state_snapshot_id",
        "household_id",
    ]
    assert [element.target_fullname for element in constraint.elements] == [
        "financial_policy_decisions.id",
        "financial_policy_decisions.financial_state_snapshot_id",
        "financial_policy_decisions.household_id",
    ]
    assert constraint.ondelete == "RESTRICT"
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_financial_policy_decisions_chain"
        and [column.name for column in item.columns]
        == ["id", "financial_state_snapshot_id", "household_id"]
        for item in FinancialPolicyDecision.__table__.constraints
    )


def test_database_constraints_enforce_nonnegative_conservation() -> None:
    checks = {
        item.name: str(item.sqltext)
        for item in CapitalAllocationDecision.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "allocated_capital + remaining_capital = allocatable_capital" in checks[
        "ck_capital_allocation_decisions_conservation"
    ]
    assert "investment_bucket_amount <= allocated_capital" in checks[
        "ck_capital_allocation_decisions_investment_bound"
    ]
    assert "allocated_capital >= 0" in checks[
        "ck_capital_allocation_decisions_nonnegative"
    ]


def test_manual_migration_is_linear_and_owned_by_alembic() -> None:
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
        "revision": "0020_capital_allocation_v1",
        "down_revision": "0019_financial_policy_v1",
    }
    assert 'op.create_table(\n        "capital_allocation_decisions"' in source
    assert 'op.drop_table("capital_allocation_decisions")' in source
    assert "autogenerate" not in source.lower()


def test_migration_has_update_delete_and_truncate_guards() -> None:
    source = _text(MIGRATION)
    assert "BEFORE UPDATE OR DELETE ON capital_allocation_decisions" in source
    assert "BEFORE TRUNCATE ON capital_allocation_decisions" in source
    assert "reject_capital_allocation_decision_mutation" in source


def test_migration_never_operates_on_external_trading_v2_tables() -> None:
    source = _text(MIGRATION).lower()
    assert all(table not in source for table in TRADING_EXTERNAL_TABLES)


def test_alembic_metadata_explicitly_registers_allocation_model() -> None:
    source = _text(ROOT / "backend" / "alembic" / "env.py")
    assert "backend.app.capital_allocation.models import CapitalAllocationDecision" in source


def test_domain_has_no_legacy_db_or_trading_execution_dependency() -> None:
    sources = "\n".join(_text(path) for path in DOMAIN.glob("*.py"))
    forbidden = (
        "db.database",
        "create_all(",
        "backend.trading",
        "paper_order",
        "recommendation_engine",
    )
    assert all(token not in sources.lower() for token in forbidden)


def test_router_exposes_only_read_and_freeze_operations() -> None:
    source = _text(DOMAIN / "router.py")
    assert source.count("@router.get(") == 4
    assert source.count("@router.post(") == 1
    assert "@router.put(" not in source
    assert "@router.patch(" not in source
    assert "@router.delete(" not in source
    assert "get_current_user" in source

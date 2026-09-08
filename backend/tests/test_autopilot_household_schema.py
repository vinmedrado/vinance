from __future__ import annotations

import ast
from pathlib import Path

from backend.app.catalog.models import AssetCatalog  # noqa: F401
from backend.app.core.database import Base
from backend.app.financial.models import Expense, Income
from backend.app.financial_state.engine import ENGINE_VERSION
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    Household,
    HouseholdMember,
    OwnedAsset,
)
from backend.alembic.schema_ownership import TRADING_EXTERNAL_TABLES


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "0018_household_financial_state_v1.py"
MODULE = ROOT / "backend" / "app" / "financial_state"


def test_household_models_share_the_only_canonical_metadata() -> None:
    expected = {
        "households",
        "household_members",
        "financial_liabilities",
        "owned_assets",
        "financial_goals",
        "financial_state_snapshots",
        "incomes",
        "expenses",
    }
    assert expected <= set(Base.metadata.tables)
    assert Household.metadata is Base.metadata
    assert HouseholdMember.metadata is Base.metadata
    assert FinancialLiability.metadata is Base.metadata
    assert OwnedAsset.metadata is Base.metadata
    assert FinancialGoal.metadata is Base.metadata
    assert FinancialStateSnapshot.metadata is Base.metadata
    assert Income.metadata is Base.metadata
    assert Expense.metadata is Base.metadata


def test_canonical_income_and_expense_are_extended_instead_of_duplicated() -> None:
    assert {"household_id", "ownership_scope"} <= set(Income.__table__.columns.keys())
    assert {"household_id", "ownership_scope", "expense_nature"} <= set(Expense.__table__.columns.keys())
    assert Income.__tablename__ == "incomes"
    assert Expense.__tablename__ == "expenses"
    assert not {"household_incomes", "household_expenses"} & set(Base.metadata.tables)


def test_owned_assets_reference_global_catalog_without_becoming_catalog_rows() -> None:
    foreign_keys = {item.target_fullname for item in OwnedAsset.__table__.foreign_keys}
    assert "asset_catalog.id" in foreign_keys
    assert OwnedAsset.__tablename__ == "owned_assets"
    assert "current_value" in OwnedAsset.__table__.columns


def test_nullable_real_world_values_remain_nullable() -> None:
    nullable_fields = {
        FinancialLiability: {
            "current_balance",
            "monthly_payment",
            "annual_interest_rate_pct",
            "due_date",
            "balance_as_of",
        },
        OwnedAsset: {"current_value", "value_as_of", "asset_catalog_id", "name"},
        FinancialGoal: {"current_amount", "deadline"},
    }
    for model, names in nullable_fields.items():
        assert all(model.__table__.columns[name].nullable for name in names)


def test_migration_is_explicitly_chained_and_does_not_touch_trading_v2() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "0018_household_state",
        "down_revision": "0017_investment_alerts",
    }
    assert not (set(TRADING_EXTERNAL_TABLES) & set(source.split('"')))
    assert "autogenerate" not in source.lower()
    assert "create_all" not in source
    assert "db.database" not in source


def test_migration_backfills_only_context_not_financial_amounts() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "LOCK TABLE users, incomes, expenses IN SHARE ROW EXCLUSIVE MODE" in source
    assert "SET household_id = household.id, ownership_scope = 'PERSONAL'" in source
    assert "SET amount" not in source
    assert "SET expense_nature" not in source
    assert "household ownership backfill left orphan financial rows" in source


def test_snapshot_storage_is_immutable_and_idempotency_aware() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE ON financial_state_snapshots" in source
    assert "BEFORE TRUNCATE ON financial_state_snapshots" in source
    assert "reject_financial_state_snapshot_mutation" in source
    assert "uq_financial_state_snapshots_idempotency" in source
    idempotency_index = next(
        index
        for index in FinancialStateSnapshot.__table__.indexes
        if index.name == "uq_financial_state_snapshots_idempotency"
    )
    assert idempotency_index.unique is True
    assert "idempotency_key IS NOT NULL" in str(idempotency_index.dialect_options["postgresql"]["where"])
    assert FinancialStateSnapshot.__table__.columns["normalized_inputs"].nullable is False
    assert FinancialStateSnapshot.__table__.columns["metrics"].nullable is False
    assert ENGINE_VERSION == "household-financial-state-v1"


def test_new_domain_has_no_market_recommendation_or_trading_dependency() -> None:
    forbidden = ("backend.trading", "backend.app.intelligence", "backend.app.recommendation")
    for path in MODULE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith(forbidden) for name in imports), path.name

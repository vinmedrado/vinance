from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

from backend.app.financial_policy.rules import (
    ENGINE_VERSION,
    PRIORITY_ORDER,
    RULE_CATALOG,
    RULES,
    RULES_VERSION,
    SUPPORTED_FINANCIAL_STATE_VERSION,
)
from backend.app.financial_state.engine import ENGINE_VERSION as STATE_ENGINE_VERSION


ROOT = Path(__file__).resolve().parents[2]
POLICY_MODULE = ROOT / "backend" / "app" / "financial_policy"
PURE_FILES = (POLICY_MODULE / "engine.py", POLICY_MODULE / "rules.py")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_engine_versions_are_explicit_and_policy_consumes_state_v1() -> None:
    assert ENGINE_VERSION == "financial-policy-v1"
    assert RULES_VERSION == "financial-policy-rules-v1"
    assert SUPPORTED_FINANCIAL_STATE_VERSION == "household-financial-state-v1"
    assert SUPPORTED_FINANCIAL_STATE_VERSION == STATE_ENGINE_VERSION


def test_every_engine_rule_is_catalogued_and_traceable() -> None:
    source = (POLICY_MODULE / "engine.py").read_text(encoding="utf-8")
    referenced = set(re.findall(r'"(FPV1-[A-Z]+-\d{3})"', source))

    assert referenced
    assert referenced <= set(RULE_CATALOG)
    assert all(description.strip() for description in RULE_CATALOG.values())


def test_thresholds_and_priority_order_are_centralized_and_frozen() -> None:
    assert RULES.minimum_policy_confidence == 50
    assert RULES.minimum_ready_confidence == 85
    assert RULES.debt_service_priority_pct == Decimal("20.00")
    assert RULES.debt_service_block_pct == Decimal("30.00")
    assert RULES.known_high_cost_debt_apr_pct == Decimal("15.00")
    assert RULES.reserve_base_months == Decimal("3.00")
    assert RULES.reserve_max_months == Decimal("6.00")
    assert list(PRIORITY_ORDER.values()) == sorted(PRIORITY_ORDER.values())


def test_pure_policy_layer_has_no_database_market_or_recommendation_dependency() -> None:
    forbidden_imports = (
        "sqlalchemy",
        "backend.app.core.database",
        "backend.app.recommendation",
        "backend.app.advisor",
        "backend.app.intelligence",
        "backend.trading",
    )
    for path in PURE_FILES:
        imports = _imports(path)
        assert not any(name.startswith(forbidden_imports) for name in imports), path.name
        source = path.read_text(encoding="utf-8")
        assert "create_all" not in source
        assert "db.database" not in source


def test_policy_does_not_define_persistence_or_universal_budget_allocations() -> None:
    assert not (POLICY_MODULE / "models.py").exists()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PURE_FILES)
    forbidden = (
        "70/20/10",
        "50/30/20",
        "ticker",
        "asset_quantity",
        "recommended_asset",
        "portfolio_weight",
    )
    assert not any(token.lower() in combined.lower() for token in forbidden)

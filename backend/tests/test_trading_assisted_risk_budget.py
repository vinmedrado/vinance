from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.trading.risk_budget import build_risk_budget
from backend.app.trading.schemas import PaperAccountCreate, PaperOrderCreate


def _context(*, readiness: str = "READY", quality: str = "COMPLETE"):
    return {
        "state": {
            "data_quality": quality,
            "decision_fingerprint": "a" * 64,
        },
        "policy": {
            "policy_state": "INVESTMENT_READY",
            "investment_readiness": readiness,
            "reserve_policy": {"status": "FUNDED"},
            "debt_policy": {"investment_blocking": False},
            "decision_fingerprint": "b" * 64,
        },
        "allocation": {
            "investment_bucket_amount": "1500.00",
            "bucket_totals": {
                "protected_capital": "500.00",
                "goal_capital": "0.00",
                "investment_capital": "1500.00",
                "speculative_capital": "0.00",
            },
            "decision_fingerprint": "c" * 64,
        },
        "orchestration": {"decision_fingerprint": "d" * 64},
    }


def test_risk_budget_never_converts_investment_bucket_to_trading_capital() -> None:
    context = _context()
    result = build_risk_budget(
        household_id=9,
        plan={
            "trading_dispatch": False,
            "speculative_capital": "0.00",
            "decision_fingerprint": "e" * 64,
        },
        context=context,
        continuous={"decision_fingerprint": "f" * 64},
    )

    assert result.paper_only is True
    assert result.paper_simulation_allowed is True
    assert result.real_trading_allowed is False
    assert result.real_trading_capital == Decimal("0.00")
    assert result.speculative_capital == Decimal("0.00")
    assert result.protected_capital == Decimal("500.00")
    assert "SPECULATIVE_CAPITAL_NOT_AUTHORIZED" in result.blocking_reasons


def test_risk_budget_financial_block_does_not_disable_learning_simulation() -> None:
    context = _context(readiness="BLOCKED", quality="INSUFFICIENT")
    context["policy"]["reserve_policy"]["status"] = "ABSENT"
    result = build_risk_budget(
        household_id=10,
        plan={"trading_dispatch": False, "speculative_capital": "0.00"},
        context=context,
        continuous={},
    )
    assert result.risk_budget_status == "DATA_BLOCKED"
    assert result.paper_simulation_allowed is True
    assert result.real_trading_allowed is False
    assert "EMERGENCY_RESERVE_ABSENT" in result.blocking_reasons


def test_public_contract_rejects_live_or_household_paper_modes() -> None:
    with pytest.raises(ValidationError):
        PaperAccountCreate(ownership_scope="HOUSEHOLD")
    with pytest.raises(ValidationError):
        PaperAccountCreate(paper_only=False)


def test_order_contract_rejects_owner_injection_live_mode_and_short_open() -> None:
    base = {
        "idempotency_key": "test-order-0001",
        "signal_id": 1,
        "symbol": "BTCUSDT",
        "notional": "100",
        "side": "BUY",
    }
    PaperOrderCreate(**base)
    with pytest.raises(ValidationError):
        PaperOrderCreate(**base, owner_user_id=99)
    with pytest.raises(ValidationError):
        PaperOrderCreate(**base, paper_only=False)
    with pytest.raises(ValidationError):
        PaperOrderCreate(**{**base, "side": "SELL"})

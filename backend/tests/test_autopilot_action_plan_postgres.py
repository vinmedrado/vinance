from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.action_plan import service as action_plan_service
from backend.app.action_plan.models import ActionPlanDecision
from backend.app.action_plan.schemas import ActionPlanRead
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.financial_policy.models import FinancialPolicyDecision
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import FinancialStateSnapshot
from backend.app.investment_orchestrator.models import InvestmentOrchestrationDecision
from backend.tests.test_autopilot_investment_orchestrator_postgres import (
    _complete_household,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


@pytest.mark.asyncio
async def test_real_postgres_action_plan_audit_idempotency_and_isolation() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            owner, outsider, household = await _complete_household(session)
            current = await action_plan_service.current_action_plan(
                session, household_id=household.id, user_id=owner.id
            )
            assert current["status"] in {"PARTIAL", "READY"}
            assert current["total_investment_actions"] <= current["summary"][
                "authorized_investment_capital"
            ]
            assert (
                current["total_investment_actions"] + current["total_hold_cash"]
                <= current["summary"]["authorized_investment_capital"]
            )
            assert Decimal(str(current["speculative_capital"])) == Decimal("0.00")
            assert current["trading_dispatch"] is False
            ActionPlanRead.model_validate(current)

            key = f"action-plan-{uuid4()}"
            frozen = await action_plan_service.create_action_plan_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=key,
            )
            retry = await action_plan_service.create_action_plan_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=key,
            )
            assert retry["action_plan_id"] == frozen["action_plan_id"]
            assert retry["decision_fingerprint"] == frozen["decision_fingerprint"]
            ActionPlanRead.model_validate(frozen)

            for model in (
                FinancialStateSnapshot,
                FinancialPolicyDecision,
                CapitalAllocationDecision,
                InvestmentOrchestrationDecision,
                ActionPlanDecision,
            ):
                assert await session.scalar(
                    select(func.count(model.id)).where(model.household_id == household.id)
                ) == 1

            history = await action_plan_service.action_plan_history(
                session,
                household_id=household.id,
                user_id=owner.id,
                limit=20,
                offset=0,
            )
            detail = await action_plan_service.get_action_plan_decision(
                session,
                household_id=household.id,
                action_plan_id=frozen["action_plan_id"],
                user_id=owner.id,
            )
            assert history["total"] == 1
            assert detail["orchestration_fingerprint"] == frozen[
                "orchestration_fingerprint"
            ]

            for mutation in (
                "UPDATE action_plan_decisions SET status = 'BLOCKED' WHERE id = :id",
                "DELETE FROM action_plan_decisions WHERE id = :id",
                "TRUNCATE TABLE action_plan_decisions",
            ):
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(
                            text(mutation), {"id": frozen["action_plan_id"]}
                        )

            stored = await session.get(ActionPlanDecision, frozen["action_plan_id"])
            assert stored is not None

            def invalid_copy(suffix: str, **overrides):
                values = {
                    "household_id": stored.household_id,
                    "financial_state_snapshot_id": stored.financial_state_snapshot_id,
                    "financial_policy_decision_id": stored.financial_policy_decision_id,
                    "capital_allocation_decision_id": stored.capital_allocation_decision_id,
                    "investment_orchestration_decision_id": stored.investment_orchestration_decision_id,
                    "created_by_user_id": stored.created_by_user_id,
                    "engine_version": f"action-plan-invalid-{suffix}",
                    "rules_version": stored.rules_version,
                    "status": stored.status,
                    "currency": stored.currency,
                    "period": stored.period,
                    "authorized_financial_capital": stored.authorized_financial_capital,
                    "investment_budget": stored.investment_budget,
                    "suggested_capital": stored.suggested_capital,
                    "remaining_investment_cash": stored.remaining_investment_cash,
                    "total_financial_actions": stored.total_financial_actions,
                    "total_investment_actions": stored.total_investment_actions,
                    "total_hold_cash": stored.total_hold_cash,
                    "speculative_capital": stored.speculative_capital,
                    "state_fingerprint": stored.state_fingerprint,
                    "policy_fingerprint": stored.policy_fingerprint,
                    "allocation_fingerprint": stored.allocation_fingerprint,
                    "orchestration_fingerprint": stored.orchestration_fingerprint,
                    "ruleset_fingerprint": stored.ruleset_fingerprint,
                    "decision_fingerprint": stored.decision_fingerprint,
                    "decision_payload": stored.decision_payload,
                    "idempotency_key": None,
                    "generated_at": stored.generated_at,
                }
                values.update(overrides)
                return ActionPlanDecision(**values)

            invalid_rows = (
                invalid_copy(
                    "financial-overflow",
                    total_financial_actions=stored.authorized_financial_capital
                    + Decimal("0.01"),
                ),
                invalid_copy(
                    "investment-overflow",
                    total_investment_actions=stored.suggested_capital
                    + Decimal("0.01"),
                ),
                invalid_copy(
                    "budget-overflow",
                    total_hold_cash=stored.investment_budget
                    - stored.total_investment_actions
                    + Decimal("0.01"),
                ),
                invalid_copy(
                    "chain-mismatch",
                    capital_allocation_decision_id=stored.capital_allocation_decision_id
                    + 1_000_000,
                ),
            )
            for invalid in invalid_rows:
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        session.add(invalid)
                        await session.flush()

            for operation in (
                action_plan_service.current_action_plan(
                    session, household_id=household.id, user_id=outsider.id
                ),
                action_plan_service.create_action_plan_decision(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    idempotency_key=f"outsider-{uuid4()}",
                ),
                action_plan_service.get_action_plan_decision(
                    session,
                    household_id=household.id,
                    action_plan_id=frozen["action_plan_id"],
                    user_id=outsider.id,
                ),
            ):
                with pytest.raises(state_service.HouseholdNotFoundError):
                    await operation
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()

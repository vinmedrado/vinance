from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.action_plan import service as action_plan_service
from backend.app.action_plan.models import ActionPlanDecision
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.continuous_autopilot import service
from backend.app.continuous_autopilot.models import (
    ContinuousAutopilotDecision,
    ContinuousAutopilotRequest,
    ContinuousAutopilotState,
)
from backend.app.financial_policy.models import FinancialPolicyDecision
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import FinancialStateSnapshot
from backend.app.financial_state.models import Household, OwnedAsset
from backend.app.intelligence.recommendation_guardrail_model import (
    AssetRecommendationGuardrail,
)
from backend.app.investment_alerts.models import InvestmentAlert
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
async def test_real_postgres_continuous_partial_chain_concurrency_and_audit() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as setup:
        owner, outsider, household = await _complete_household(setup)
        baseline = await service.evaluate_continuous_autopilot(
            setup,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-baseline-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        retry_key = f"continuous-market-{uuid4()}"
        guardrail = await setup.scalar(
            select(AssetRecommendationGuardrail)
            .where(AssetRecommendationGuardrail.status == "APPROVED")
            .order_by(AssetRecommendationGuardrail.id.desc())
            .limit(1)
        )
        assert guardrail is not None
        guardrail.status = "BLOCKED"
        await service.mark_household_dirty(
            setup,
            household_id=household.id,
            category="MARKET_DATA",
            dirty_at=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
        )
        await setup.commit()
        owner_id = owner.id
        outsider_id = outsider.id
        household_id = household.id

    async def evaluate_once() -> dict:
        async with sessions() as concurrent:
            return await service.evaluate_continuous_autopilot(
                concurrent,
                household_id=household_id,
                user_id=owner_id,
                idempotency_key=retry_key,
                as_of=datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc),
                change_categories=["MARKET_DATA"],
            )

    first, second = await asyncio.gather(evaluate_once(), evaluate_once())
    assert first["continuous_decision_id"] == second["continuous_decision_id"]
    assert first["decision_fingerprint"] == second["decision_fingerprint"]
    assert first["reevaluation_scope"] == "INVESTMENT_CHAIN"

    async with sessions() as verify:
        current_plan = await verify.get(
            ActionPlanDecision, first["current_action_plan_id"]
        )
        previous_plan = await verify.get(
            ActionPlanDecision, baseline["current_action_plan_id"]
        )
        assert current_plan is not None and previous_plan is not None
        assert (
            current_plan.financial_state_snapshot_id
            == previous_plan.financial_state_snapshot_id
        )
        assert (
            current_plan.financial_policy_decision_id
            == previous_plan.financial_policy_decision_id
        )
        assert (
            current_plan.capital_allocation_decision_id
            == previous_plan.capital_allocation_decision_id
        )
        assert (
            current_plan.investment_orchestration_decision_id
            != previous_plan.investment_orchestration_decision_id
        )

        assert await verify.scalar(
            select(func.count(FinancialStateSnapshot.id)).where(
                FinancialStateSnapshot.household_id == household_id
            )
        ) == 1
        assert await verify.scalar(
            select(func.count(FinancialPolicyDecision.id)).where(
                FinancialPolicyDecision.household_id == household_id
            )
        ) == 1
        assert await verify.scalar(
            select(func.count(CapitalAllocationDecision.id)).where(
                CapitalAllocationDecision.household_id == household_id
            )
        ) == 1
        assert await verify.scalar(
            select(func.count(InvestmentOrchestrationDecision.id)).where(
                InvestmentOrchestrationDecision.household_id == household_id
            )
        ) == 2
        assert await verify.scalar(
            select(func.count(ActionPlanDecision.id)).where(
                ActionPlanDecision.household_id == household_id
            )
        ) == 2
        assert await verify.scalar(
            select(func.count(ContinuousAutopilotDecision.id)).where(
                ContinuousAutopilotDecision.household_id == household_id
            )
        ) == 2
        assert await verify.scalar(
            select(func.count()).select_from(ContinuousAutopilotRequest).where(
                ContinuousAutopilotRequest.household_id == household_id,
                ContinuousAutopilotRequest.idempotency_key == retry_key,
            )
        ) == 1
        assert await verify.scalar(
            select(func.count(InvestmentAlert.id)).where(
                InvestmentAlert.household_id == household_id,
                InvestmentAlert.continuous_decision_id
                == first["continuous_decision_id"],
            )
        ) <= 1

        operational = await verify.get(ContinuousAutopilotState, household_id)
        assert operational is not None
        assert operational.pending_categories == []
        assert operational.last_action_plan_id == first["current_action_plan_id"]

        for mutation in (
            "UPDATE continuous_autopilot_decisions SET status = 'FAILED' WHERE id = :id",
            "DELETE FROM continuous_autopilot_decisions WHERE id = :id",
            "TRUNCATE TABLE continuous_autopilot_decisions",
        ):
            with pytest.raises(DBAPIError):
                async with verify.begin_nested():
                    await verify.execute(
                        text(mutation), {"id": first["continuous_decision_id"]}
                    )

        for mutation in (
            "UPDATE continuous_autopilot_requests SET request_fingerprint = "
            "repeat('f', 64) WHERE household_id = :household_id "
            "AND idempotency_key = :key",
            "DELETE FROM continuous_autopilot_requests WHERE household_id = "
            ":household_id AND idempotency_key = :key",
            "TRUNCATE TABLE continuous_autopilot_requests",
        ):
            with pytest.raises(DBAPIError):
                async with verify.begin_nested():
                    await verify.execute(
                        text(mutation),
                        {"household_id": household_id, "key": retry_key},
                    )

        with pytest.raises(state_service.HouseholdNotFoundError):
            await service.get_continuous_autopilot_decision(
                verify,
                household_id=household_id,
                continuous_decision_id=first["continuous_decision_id"],
                user_id=outsider_id,
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_idempotency_alias_survives_dirty_state() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    transition_key = f"continuous-alias-transition-{uuid4()}"
    first_key = f"continuous-alias-first-{uuid4()}"
    alias_key = f"continuous-alias-second-{uuid4()}"
    first_at = datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)

    async with sessions() as session:
        owner, _outsider, household = await _complete_household(session)
        await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-alias-baseline-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=transition_key,
            as_of=first_at,
            change_categories=["MARKET_DATA"],
        )
        first = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=first_key,
            as_of=first_at,
            change_categories=["MARKET_DATA"],
        )
        alias = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=alias_key,
            as_of=first_at,
            change_categories=["MARKET_DATA"],
        )
        assert alias["continuous_decision_id"] == first["continuous_decision_id"]
        requests = (
            await session.execute(
                select(ContinuousAutopilotRequest).where(
                    ContinuousAutopilotRequest.household_id == household.id,
                    ContinuousAutopilotRequest.idempotency_key.in_(
                        [first_key, alias_key]
                    ),
                )
            )
        ).scalars().all()
        assert len(requests) == 2
        assert {item.continuous_decision_id for item in requests} == {
            first["continuous_decision_id"]
        }

        await service.mark_household_dirty(
            session,
            household_id=household.id,
            category="MARKET_DATA",
            dirty_at=datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc),
        )
        await session.commit()
        state = await session.get(ContinuousAutopilotState, household.id)
        assert state is not None
        evaluation_count = state.evaluation_count

        replay = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=alias_key,
            as_of=first_at,
            change_categories=["MARKET_DATA"],
        )
        assert replay["continuous_decision_id"] == first["continuous_decision_id"]
        assert replay["operational_status"] == "REEVALUATION_REQUIRED"
        await session.refresh(state)
        assert state.pending_categories == ["MARKET_DATA"]
        assert state.evaluation_count == evaluation_count

        with pytest.raises(service.ContinuousAutopilotConflictError):
            await service.evaluate_continuous_autopilot(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=alias_key,
                as_of=datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc),
                change_categories=["MARKET_DATA"],
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_profile_and_freshness_recompute_full_chain() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        owner, _outsider, household = await _complete_household(session)
        for model in (Income, OwnedAsset):
            rows = (
                await session.execute(
                    select(model).where(model.household_id == household.id)
                )
            ).scalars().all()
            for row in rows:
                await session.delete(row)
        profile = await session.scalar(
            select(FinancialProfile).where(FinancialProfile.user_id == owner.id)
        )
        assert profile is not None
        profile.emergency_reserve = Decimal("0")
        await service.mark_household_dirty(
            session,
            household_id=household.id,
            category="PROFILE",
            dirty_at=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
        )
        await session.commit()

        baseline = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-profile-baseline-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["PROFILE"],
        )
        assert baseline["reevaluation_scope"] == "FULL_CHAIN"

        profile = await session.scalar(
            select(FinancialProfile).where(FinancialProfile.user_id == owner.id)
        )
        assert profile is not None
        profile.emergency_reserve = Decimal("12000")
        profile.risk_profile = "CONSERVATIVE"
        await service.mark_household_dirty(
            session,
            household_id=household.id,
            category="PROFILE",
            dirty_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        )
        await session.commit()
        changed = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-profile-change-{uuid4()}",
            as_of=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
            change_categories=["PROFILE"],
        )
        assert changed["reevaluation_scope"] == "FULL_CHAIN"
        baseline_plan = await session.get(
            ActionPlanDecision, baseline["current_action_plan_id"]
        )
        current_plan = await session.get(ActionPlanDecision, changed["current_action_plan_id"])
        assert baseline_plan is not None and current_plan is not None
        assert (
            current_plan.financial_state_snapshot_id
            != baseline_plan.financial_state_snapshot_id
        )
        current_state = await session.get(
            FinancialStateSnapshot, current_plan.financial_state_snapshot_id
        )
        assert current_state is not None
        assert Decimal(str(current_state.metrics["emergency_reserve"])) == Decimal(
            "12000.00"
        )

    async with sessions() as stale_session:
        owner, _outsider, household = await _complete_household(stale_session)
        baseline = await service.evaluate_continuous_autopilot(
            stale_session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-fresh-baseline-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        await service.mark_household_dirty(
            stale_session,
            household_id=household.id,
            category="FRESHNESS",
            dirty_at=datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
        )
        await stale_session.commit()
        stale = await service.evaluate_continuous_autopilot(
            stale_session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-fresh-stale-{uuid4()}",
            as_of=datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
            change_categories=["FRESHNESS"],
        )
        assert stale["reevaluation_scope"] == "FULL_CHAIN"
        assert stale["current_action_plan_id"] != baseline["current_action_plan_id"]
        stale_plan = await stale_session.get(
            ActionPlanDecision, stale["current_action_plan_id"]
        )
        assert stale_plan is not None
        stale_state = await stale_session.get(
            FinancialStateSnapshot, stale_plan.financial_state_snapshot_id
        )
        assert stale_state is not None
        assert stale_state.data_quality == "STALE"

    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_uses_monitored_plan_and_skips_archived_households() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        owner, _outsider, household = await _complete_household(session)
        baseline = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-monitored-baseline-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        expense = await session.scalar(
            select(Expense)
            .where(Expense.household_id == household.id)
            .order_by(Expense.id.asc())
            .limit(1)
        )
        assert expense is not None
        expense.amount = Decimal("7000")
        await service.mark_household_dirty(
            session,
            household_id=household.id,
            category="FINANCIAL_DATA",
            dirty_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        )
        await session.commit()
        external = await action_plan_service.create_action_plan_decision(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"external-action-plan-{uuid4()}",
            evaluated_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        )
        assert external["action_plan_id"] != baseline["current_action_plan_id"]

        changed = await service.evaluate_continuous_autopilot(
            session,
            household_id=household.id,
            user_id=owner.id,
            idempotency_key=f"continuous-monitored-change-{uuid4()}",
            as_of=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        assert changed["previous_action_plan_id"] == baseline["current_action_plan_id"]
        assert changed["previous_action_plan_id"] != external["action_plan_id"]
        assert changed["current_action_plan_id"] != baseline["current_action_plan_id"]

        archived = await session.get(Household, household.id)
        assert archived is not None
        archived.status = "ARCHIVED"
        await session.commit()
        scheduled = await service.scheduled_households(session, limit=1000)
        assert household.id not in {item[0] for item in scheduled}

    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_rejects_cross_household_operational_links() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        owner_a, _outsider_a, household_a = await _complete_household(session)
        owner_b, _outsider_b, household_b = await _complete_household(session)
        decision_a = await service.evaluate_continuous_autopilot(
            session,
            household_id=household_a.id,
            user_id=owner_a.id,
            idempotency_key=f"continuous-fk-a-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )
        decision_b = await service.evaluate_continuous_autopilot(
            session,
            household_id=household_b.id,
            user_id=owner_b.id,
            idempotency_key=f"continuous-fk-b-{uuid4()}",
            as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
            change_categories=["FINANCIAL_DATA"],
        )

        invalid_statements = [
            (
                "UPDATE continuous_autopilot_states SET last_action_plan_id = :plan "
                "WHERE household_id = :household",
                {
                    "plan": decision_b["current_action_plan_id"],
                    "household": household_a.id,
                },
            ),
            (
                "UPDATE continuous_autopilot_states SET "
                "last_continuous_decision_id = :decision, "
                "last_action_plan_id = :plan WHERE household_id = :household",
                {
                    "decision": decision_b["continuous_decision_id"],
                    "plan": decision_b["current_action_plan_id"],
                    "household": household_a.id,
                },
            ),
            (
                "INSERT INTO continuous_autopilot_requests "
                "(household_id, idempotency_key, continuous_decision_id, "
                "request_fingerprint) VALUES (:household, :key, :decision, "
                "repeat('a', 64))",
                {
                    "household": household_a.id,
                    "key": f"cross-request-{uuid4()}",
                    "decision": decision_b["continuous_decision_id"],
                },
            ),
        ]
        for statement, params in invalid_statements:
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(text(statement), params)

        alert_insert = text(
            """
            INSERT INTO investment_alerts
                (alert_id, deduplication_key, user_id, subscription_id,
                 decision_id, asset, source_domain, source_reference,
                 household_id, continuous_decision_id, ownership_scope,
                 owner_user_id, alert_type, severity, delivery_channel,
                 previous_state, current_state, message, rule_version)
            VALUES
                (:alert_id, :dedupe, :user_id, NULL, NULL, NULL,
                 'CONTINUOUS_AUTOPILOT', :source_reference, :household_id,
                 :continuous_decision_id, :ownership_scope, :owner_user_id,
                 'CONTINUOUS_AUTOPILOT_CHANGE', 'HIGH', 'IN_APP',
                 '{}'::json, '{}'::json, 'Mudança relevante.',
                 'continuous-autopilot-rules-v1')
            """
        )
        alert_cases = [
            {
                "alert_id": str(uuid4()),
                "dedupe": uuid4().hex * 2,
                "user_id": owner_a.id,
                "source_reference": "cross-decision",
                "household_id": household_a.id,
                "continuous_decision_id": decision_b["continuous_decision_id"],
                "ownership_scope": "HOUSEHOLD",
                "owner_user_id": None,
            },
            {
                "alert_id": str(uuid4()),
                "dedupe": uuid4().hex * 2,
                "user_id": owner_b.id,
                "source_reference": "cross-recipient",
                "household_id": household_a.id,
                "continuous_decision_id": decision_a["continuous_decision_id"],
                "ownership_scope": "HOUSEHOLD",
                "owner_user_id": None,
            },
            {
                "alert_id": str(uuid4()),
                "dedupe": uuid4().hex * 2,
                "user_id": owner_a.id,
                "source_reference": "cross-owner",
                "household_id": household_a.id,
                "continuous_decision_id": decision_a["continuous_decision_id"],
                "ownership_scope": "PERSONAL",
                "owner_user_id": owner_b.id,
            },
        ]
        for params in alert_cases:
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(alert_insert, params)

    await engine.dispose()

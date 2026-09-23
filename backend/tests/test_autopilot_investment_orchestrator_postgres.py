from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.auth import service as auth_service
from backend.app.auth.schemas import UserCreate
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.catalog.models import AssetCatalog
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial_policy.models import FinancialPolicyDecision
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    OwnedAsset,
)
from backend.app.financial_state.schemas import (
    AssetCreate,
    ExpenseCreate,
    GoalCreate,
    IncomeCreate,
    LiabilityCreate,
)
from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.recommendation_guardrail_model import (
    AssetRecommendationGuardrail,
)
from backend.app.intelligence.services.asset_score_service import SCORE_SOURCE
from backend.app.intelligence.services.recommendation_guardrail_service import (
    GUARDRAIL_SOURCE,
)
from backend.app.investment_orchestrator import service as orchestration_service
from backend.app.investment_orchestrator.models import InvestmentOrchestrationDecision
from backend.app.investment_orchestrator.schemas import InvestmentOrchestrationRead


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


async def _complete_household(session: AsyncSession):
    owner = await auth_service.create_user(
        session,
        UserCreate(
            email=f"orchestration-owner-{uuid4()}@example.com",
            password="senha-segura",
            full_name="Orchestration Owner",
        ),
    )
    outsider = await auth_service.create_user(
        session,
        UserCreate(
            email=f"orchestration-outsider-{uuid4()}@example.com",
            password="senha-segura",
            full_name="Orchestration Outsider",
        ),
    )
    household = await state_service.get_default_household(session, user_id=owner.id)
    session.add(
        FinancialProfile(
            user_id=owner.id,
            monthly_salary=Decimal("6000"),
            emergency_reserve=Decimal("12000"),
            has_debt_default=False,
            risk_profile="MODERATE",
        )
    )
    await session.commit()
    await state_service.create_resource(
        session,
        Income,
        household_id=household.id,
        user_id=owner.id,
        payload=IncomeCreate(
            ownership_scope="PERSONAL",
            description="Renda recorrente",
            amount=Decimal("6000"),
            income_type="salary",
            received_at=date(2026, 9, 22),
            is_recurring=True,
        ),
    )
    await state_service.create_resource(
        session,
        Income,
        household_id=household.id,
        user_id=owner.id,
        payload=IncomeCreate(
            ownership_scope="PERSONAL",
            description="Renda não recorrente declarada",
            amount=Decimal("0"),
            income_type="declared_none",
            received_at=date(2026, 9, 22),
            is_recurring=False,
        ),
    )
    for nature in ("FIXED", "VARIABLE"):
        await state_service.create_resource(
            session,
            Expense,
            household_id=household.id,
            user_id=owner.id,
            payload=ExpenseCreate(
                ownership_scope="PERSONAL",
                description=f"Despesa {nature.lower()}",
                amount=Decimal("1000"),
                category="declared",
                due_date=date(2026, 9, 22),
                is_recurring=True,
                expense_nature=nature,
            ),
        )
    await state_service.create_resource(
        session,
        OwnedAsset,
        household_id=household.id,
        user_id=owner.id,
        payload=AssetCreate(
            ownership_scope="PERSONAL",
            asset_class="EMERGENCY_RESERVE",
            name="Reserva",
            current_value=Decimal("12000"),
            value_as_of=date(2026, 9, 22),
        ),
    )
    await state_service.create_resource(
        session,
        FinancialLiability,
        household_id=household.id,
        user_id=owner.id,
        payload=LiabilityCreate(
            ownership_scope="PERSONAL",
            name="Obrigação quitada",
            liability_type="loan",
            current_balance=Decimal("0"),
            monthly_payment=Decimal("0"),
            annual_interest_rate_pct=Decimal("0"),
            status="PAID",
        ),
    )
    await state_service.create_resource(
        session,
        FinancialGoal,
        household_id=household.id,
        user_id=owner.id,
        payload=GoalCreate(
            ownership_scope="PERSONAL",
            name="Objetivo financiado",
            target_amount=Decimal("100"),
            current_amount=Decimal("100"),
            priority="LOW",
        ),
    )
    ticker = f"A4{uuid4().hex[:6].upper()}"
    catalog = AssetCatalog(
        ticker=ticker,
        name="Autopilot 4 Test Asset",
        market="ACOES",
        currency="BRL",
        source="autopilot-test",
        is_active=True,
    )
    session.add(catalog)
    session.add(
        AssetScore(
            ticker=ticker,
            market="ACOES",
            date=datetime.now(timezone.utc).date(),
            score_total=Decimal("82"),
            score_value=Decimal("80"),
            score_quality=Decimal("85"),
            score_dividend=Decimal("70"),
            score_liquidity=Decimal("90"),
            score_risk=Decimal("80"),
            price=Decimal("100"),
            metadata_json={"test": True},
            source=SCORE_SOURCE,
        )
    )
    session.add(
        AssetRecommendationGuardrail(
            ticker=ticker,
            market="ACOES",
            date=datetime.now(timezone.utc).date(),
            status="APPROVED",
            risk_level="LOW",
            penalty_score=Decimal("0"),
            reasons_json={"blocked": [], "warnings": [], "summary": []},
            source=GUARDRAIL_SOURCE,
        )
    )
    await session.commit()
    return owner, outsider, household


@pytest.mark.asyncio
async def test_real_postgres_orchestration_audit_idempotency_and_isolation() -> None:
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
            current = await orchestration_service.current_investment_orchestration(
                session, household_id=household.id, user_id=owner.id
            )
            assert current["status"] in {"LIMITED", "ACTIVE"}
            assert current["investment_budget"] == Decimal("4000.00")
            assert current["suggested_capital"] <= current["investment_budget"]
            assert current["trading_dispatch"] is False
            InvestmentOrchestrationRead.model_validate(current)

            key = f"orchestration-{uuid4()}"
            frozen = await orchestration_service.create_investment_orchestration_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=key,
            )
            retry = await orchestration_service.create_investment_orchestration_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=key,
            )
            assert retry["orchestration_id"] == frozen["orchestration_id"]
            assert retry["decision_fingerprint"] == frozen["decision_fingerprint"]
            assert Decimal(str(frozen["speculative_capital"])) == Decimal("0.00")
            InvestmentOrchestrationRead.model_validate(frozen)

            for model in (
                FinancialStateSnapshot,
                FinancialPolicyDecision,
                CapitalAllocationDecision,
                InvestmentOrchestrationDecision,
            ):
                assert await session.scalar(
                    select(func.count(model.id)).where(model.household_id == household.id)
                ) == 1

            history = await orchestration_service.investment_orchestration_history(
                session,
                household_id=household.id,
                user_id=owner.id,
                limit=20,
                offset=0,
            )
            detail = await orchestration_service.get_investment_orchestration_decision(
                session,
                household_id=household.id,
                orchestration_id=frozen["orchestration_id"],
                user_id=owner.id,
            )
            assert history["total"] == 1
            assert detail["market_context_fingerprint"] == frozen["market_context_fingerprint"]

            for mutation in (
                "UPDATE investment_orchestration_decisions SET status = 'BLOCKED' WHERE id = :id",
                "DELETE FROM investment_orchestration_decisions WHERE id = :id",
                "TRUNCATE TABLE investment_orchestration_decisions",
            ):
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(text(mutation), {"id": frozen["orchestration_id"]})

            for operation in (
                orchestration_service.current_investment_orchestration(
                    session, household_id=household.id, user_id=outsider.id
                ),
                orchestration_service.create_investment_orchestration_decision(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    idempotency_key=f"outsider-{uuid4()}",
                ),
                orchestration_service.get_investment_orchestration_decision(
                    session,
                    household_id=household.id,
                    orchestration_id=frozen["orchestration_id"],
                    user_id=outsider.id,
                ),
            ):
                with pytest.raises(state_service.HouseholdNotFoundError):
                    await operation
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()

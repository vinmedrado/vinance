from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.trading import repository, service
from backend.app.trading.errors import TradingNotFoundError
from backend.app.trading.schemas import (
    IdempotentAction,
    PaperAccountCreate,
    PaperOrderCreate,
    TradingRiskBudgetRead,
)


TEST_DATABASE_URL = os.getenv("TRADING_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set TRADING_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


def _assert_isolated_database() -> None:
    assert TEST_DATABASE_URL is not None
    assert "test" in (make_url(TEST_DATABASE_URL).database or "").lower()


async def _create_user(session, label: str) -> int:
    result = await session.execute(
        text(
            """
            INSERT INTO users (email, full_name, hashed_password, is_active)
            VALUES (:email, :full_name, 'not-used', TRUE)
            RETURNING id
            """
        ),
        {"email": f"{label}-{uuid4()}@example.com", "full_name": label},
    )
    await session.commit()
    return int(result.scalar_one())


def _budget(household_id: int) -> TradingRiskBudgetRead:
    return TradingRiskBudgetRead(
        paper_simulation_allowed=True,
        financial_status="TEST:PAPER_ONLY",
        risk_budget_status="PAPER_ONLY",
        protected_capital=Decimal("1000"),
        blocking_reasons=["REAL_TRADING_NOT_SUPPORTED"],
        context_fingerprints={"state": "test-state"},
        household_id=household_id,
        simulation_rules={"rules_apply_to_virtual_balance_only": True},
    )


@pytest.mark.asyncio
async def test_personal_owner_and_paper_only_constraints() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        user_a = await _create_user(session, "paper-owner-a")
        user_b = await _create_user(session, "paper-owner-b")
        user_c = await _create_user(session, "paper-owner-c")
        account_a = await service.create_paper_account(
            session, user_id=user_a, payload=PaperAccountCreate()
        )
        account_b = await service.create_paper_account(
            session, user_id=user_b, payload=PaperAccountCreate()
        )
        assert account_a.owner_user_id == user_a
        assert account_b.owner_user_id == user_b
        assert account_a.paper_only is True
        assert account_a.ownership_scope == "PERSONAL"
        visible_to_b = await repository.get_account(session, owner_user_id=user_b)
        assert visible_to_b is not None
        assert int(visible_to_b["id"]) == account_b.id
        assert int(visible_to_b["id"]) != account_a.id

        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO trading_paper_accounts (
                        owner_user_id, ownership_scope, status, quote_asset,
                        initial_virtual_balance, cash, equity, peak_equity,
                        ruleset_version, paper_only
                    ) VALUES (
                        :owner, 'HOUSEHOLD', 'ACTIVE', 'USDT',
                        10000, 10000, 10000, 10000, 'test', FALSE
                    )
                    """
                ),
                {"owner": user_c},
            )
            await session.commit()
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_order_idempotency_concurrency_and_restart_recovery(monkeypatch) -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        user_id = await _create_user(session, "paper-lifecycle")
        await service.create_paper_account(
            session, user_id=user_id, payload=PaperAccountCreate()
        )
        candle = await session.execute(
            text(
                """
                INSERT INTO crypto_candles (
                    exchange, symbol, interval, open_time, close_time,
                    open, high, low, close, volume
                ) VALUES (
                    'test', 'BTCUSDT', '5m', :now, :now,
                    100, 101, 99, 100, 1
                ) RETURNING id
                """
            ),
            {"now": datetime.now(timezone.utc)},
        )
        candle_id = int(candle.scalar_one())
        reason = {
            "model_id": "paper-active-test-model",
            "model_name": "test-model",
            "probability_take_profit": 0.80,
            "probability_stop_loss": 0.10,
            "probability_neutral": 0.10,
            "confidence": 0.80,
            "paper_only": True,
        }
        signal = await session.execute(
            text(
                """
                INSERT INTO trading_signals (
                    symbol, interval, signal_time, model_version, side,
                    probability, score, reason, prediction_id, candle_id,
                    feature_version, target_version, target_name,
                    reference_price, freshness_expires_at,
                    guardrail_status, paper_only
                ) VALUES (
                    'BTCUSDT', '5m', :now, 'model-v1', 'BUY_CANDIDATE',
                    0.80, 0.80, CAST(:reason AS JSONB), :prediction_id, :candle_id,
                    'v2', 'v2', 'v2_long_tp_100bps_sl_50bps_h_24', 100, :expires_at,
                    'APPROVED', TRUE
                ) RETURNING id
                """
            ),
            {
                "now": datetime.now(timezone.utc),
                "reason": json.dumps(reason),
                "prediction_id": f"prediction-{uuid4()}",
                "candle_id": candle_id,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            },
        )
        signal_id = int(signal.scalar_one())
        await session.commit()

    async def fake_budget(_session, *, household_id: int, user_id: int):
        del _session, user_id
        return _budget(household_id)

    monkeypatch.setattr(service, "current_trading_risk_budget", fake_budget)
    monkeypatch.setattr(
        service,
        "_active_registry_model",
        lambda _reason: SimpleNamespace(version="model-v1"),
    )
    idempotency_key = f"open-{uuid4()}"
    payload = PaperOrderCreate(
        idempotency_key=idempotency_key,
        signal_id=signal_id,
        symbol="BTCUSDT",
        side="BUY",
        notional=Decimal("100"),
    )

    async def create_once():
        async with sessions() as session:
            return await service.create_order(
                session,
                user_id=user_id,
                household_id=1,
                payload=payload,
            )

    first, second = await asyncio.gather(create_once(), create_once())
    assert first.id == second.id

    async with sessions() as session:
        orders = await service.list_paper_orders(
            session, user_id=user_id, status=None, limit=20, offset=0
        )
        positions = await service.list_paper_positions(
            session, user_id=user_id, status="OPEN", limit=20, offset=0
        )
        events = await service.list_paper_events(
            session, user_id=user_id, limit=50, offset=0
        )
        assert orders.total == 1
        assert positions.total == 1
        assert events.total >= 3
        position_id = int(positions.items[0]["id"])

    # A fresh engine simulates an application restart: no lifecycle state may
    # depend on the in-memory executor.
    await engine.dispose()
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    close_key = f"close-{uuid4()}"

    async def close_once():
        async with sessions() as session:
            return await service.close_position(
                session,
                user_id=user_id,
                position_id=position_id,
                payload=IdempotentAction(idempotency_key=close_key),
            )

    closed_first, closed_second = await asyncio.gather(close_once(), close_once())
    assert closed_first.id == closed_second.id == position_id
    assert closed_first.status == closed_second.status == "CLOSED"
    async with sessions() as session:
        repeated = await service.close_position(
            session,
            user_id=user_id,
            position_id=position_id,
            payload=IdempotentAction(idempotency_key=close_key),
        )
        assert repeated.status == "CLOSED"
        account = await service.get_paper_account(session, user_id=user_id)
        assert account.realized_pnl < 0  # fees/slippage are modeled explicitly
        assert account.paper_only is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_pending_order_cancel_is_concurrency_safe() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        user_id = await _create_user(session, "paper-cancel-concurrency")
        account = await service.create_paper_account(
            session, user_id=user_id, payload=PaperAccountCreate()
        )
        order = await repository.insert_order(
            session,
            values={
                "paper_account_id": account.id,
                "owner_user_id": user_id,
                "idempotency_key": f"pending-{uuid4()}",
                "request_fingerprint": "a" * 64,
                "correlation_id": str(uuid4()),
                "signal_id": None,
                "prediction_id": None,
                "symbol": "BTCUSDT",
                "market": "CRYPTO",
                "interval": "5m",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": Decimal("1"),
                "notional": Decimal("100"),
                "reference_price": Decimal("100"),
                "limit_price": Decimal("90"),
                "stop_price": Decimal("95"),
                "target_price": Decimal("110"),
                "status": "PENDING",
                "model_version": None,
                "feature_version": None,
                "target_version": None,
                "risk_decision": "PAPER_APPROVED",
                "risk_snapshot": {"paper_only": True},
                "financial_fingerprints": {},
                "filled_at": None,
                "fee_paid": Decimal("0"),
            },
        )
        await session.commit()

    cancel_payload = IdempotentAction(idempotency_key=f"cancel-{uuid4()}")

    async def cancel_once():
        async with sessions() as session:
            return await service.cancel_order(
                session,
                user_id=user_id,
                order_id=int(order["id"]),
                payload=cancel_payload,
            )

    first, second = await asyncio.gather(cancel_once(), cancel_once())
    assert first.id == second.id == int(order["id"])
    assert first.status == second.status == "CANCELLED"
    async with sessions() as session:
        events = await service.list_paper_events(
            session, user_id=user_id, limit=50, offset=0
        )
        cancel_events = [
            item for item in events.items if item["event_type"] == "PAPER_ORDER_CANCELLED"
        ]
        assert len(cancel_events) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_cross_user_cannot_read_or_mutate_paper_resources() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        owner = await _create_user(session, "paper-private-owner")
        outsider = await _create_user(session, "paper-private-outsider")
        owner_account = await service.create_paper_account(
            session, user_id=owner, payload=PaperAccountCreate()
        )
        await service.create_paper_account(
            session, user_id=outsider, payload=PaperAccountCreate()
        )
        order = await repository.insert_order(
            session,
            values={
                "paper_account_id": owner_account.id,
                "owner_user_id": owner,
                "idempotency_key": f"private-{uuid4()}",
                "request_fingerprint": "b" * 64,
                "correlation_id": str(uuid4()),
                "signal_id": None,
                "prediction_id": None,
                "symbol": "BTCUSDT",
                "market": "CRYPTO",
                "interval": "5m",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": Decimal("1"),
                "notional": Decimal("100"),
                "reference_price": Decimal("100"),
                "limit_price": Decimal("90"),
                "stop_price": Decimal("95"),
                "target_price": Decimal("110"),
                "status": "PENDING",
                "model_version": None,
                "feature_version": None,
                "target_version": None,
                "risk_decision": "PAPER_APPROVED",
                "risk_snapshot": {"paper_only": True},
                "financial_fingerprints": {},
                "filled_at": None,
                "fee_paid": Decimal("0"),
            },
        )
        position = await repository.insert_position(
            session,
            values={
                "paper_account_id": owner_account.id,
                "owner_user_id": owner,
                "symbol": "BTCUSDT",
                "market": "CRYPTO",
                "interval": "5m",
                "side": "LONG",
                "quantity": Decimal("1"),
                "average_entry_price": Decimal("100"),
                "current_reference_price": Decimal("100"),
                "entry_fee": Decimal("0.10"),
                "stop_price": Decimal("95"),
                "target_price": Decimal("110"),
                "opening_order_id": order["id"],
            },
        )
        await repository.insert_event(
            session,
            values={
                "owner_user_id": owner,
                "paper_account_id": owner_account.id,
                "event_type": "PAPER_POSITION_OPENED",
                "signal_id": None,
                "prediction_id": None,
                "order_id": order["id"],
                "position_id": position["id"],
                "symbol": "BTCUSDT",
                "event_payload": {"paper_only": True},
                "decision_context": {},
                "risk_context": {},
                "correlation_id": str(uuid4()),
            },
        )
        await session.commit()

        assert await repository.get_order(
            session, order_id=int(order["id"]), owner_user_id=outsider
        ) is None
        assert await repository.get_position(
            session, position_id=int(position["id"]), owner_user_id=outsider
        ) is None
        outsider_events = await service.list_paper_events(
            session, user_id=outsider, limit=50, offset=0
        )
        assert outsider_events.total == 1  # only the outsider's account-created event

        with pytest.raises(TradingNotFoundError):
            await service.cancel_order(
                session,
                user_id=outsider,
                order_id=int(order["id"]),
                payload=IdempotentAction(idempotency_key=f"cancel-{uuid4()}"),
            )
        with pytest.raises(TradingNotFoundError):
            await service.close_position(
                session,
                user_id=outsider,
                position_id=int(position["id"]),
                payload=IdempotentAction(idempotency_key=f"close-{uuid4()}"),
            )
    await engine.dispose()

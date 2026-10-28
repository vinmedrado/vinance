from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.trading.config import get_settings as get_trading_settings
from backend.trading.paper_trading_v2.config import DEFAULT_CONFIG
from backend.trading.paper_trading_v2.executor import (
    PaperTradingExecutor,
    parse_target_name,
)
from backend.trading.paper_trading_v2.models import PortfolioState
from backend.trading.paper_trading_v2.risk import PaperRiskManager
from backend.trading.prediction_engine.decision import BUY_CANDIDATE
from backend.trading.prediction_engine.models import PredictionResult
from backend.trading.model_registry import get_registry

from . import repository
from .errors import (
    TradingConflictError,
    TradingDataUnavailableError,
    TradingNotFoundError,
    TradingPaperOnlyError,
    TradingValidationError,
)
from .risk_budget import current_trading_risk_budget
from .rules import RULES
from .schemas import (
    IdempotentAction,
    PaperAccountCreate,
    PaperAccountRead,
    PaperEventRead,
    PaperOrderCreate,
    PaperOrderRead,
    PaperPositionRead,
    TradingBacktestRead,
    TradingHealthRead,
    TradingListResponse,
    TradingModelRead,
    TradingOpportunityRead,
    TradingOverviewRead,
    TradingRiskBudgetRead,
    TradingSignalRead,
)


MONEY_QUANT = Decimal("0.000000000001")


def _paper_only() -> None:
    if get_trading_settings().trading_mode != "PAPER_ONLY" or not DEFAULT_CONFIG.paper_only:
        raise TradingPaperOnlyError("Trading API requires server-side PAPER_ONLY mode")


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return dict(value or {})


def _account_read(value: Mapping[str, Any]) -> PaperAccountRead:
    return PaperAccountRead.model_validate(dict(value))


def _order_read(value: Mapping[str, Any]) -> PaperOrderRead:
    payload = dict(value)
    payload["risk_snapshot"] = _json_dict(payload.get("risk_snapshot"))
    payload["financial_fingerprints"] = _json_dict(payload.get("financial_fingerprints"))
    return PaperOrderRead.model_validate(payload)


def _position_read(value: Mapping[str, Any]) -> PaperPositionRead:
    return PaperPositionRead.model_validate(dict(value))


def _event_read(value: Mapping[str, Any]) -> PaperEventRead:
    payload = dict(value)
    projections = {
        "event_payload": {
            "quote_asset", "initial_virtual_balance", "paper_only", "order_status",
            "quantity", "entry_price", "entry_fee", "exit_price", "realized_pnl",
            "fees", "status", "reason",
        },
        "decision_context": {
            "ownership_scope", "model_version", "feature_version", "target_name",
            "signal_id", "reason",
        },
        "risk_context": {
            "ruleset_version", "paper_engine_version", "max_notional", "entry_fee",
            "exit_fee", "risk_reason", "real_trading_allowed",
            "real_trading_capital", "paper_only", "reference_price_max_age_seconds",
        },
    }
    for field, allowed in projections.items():
        raw = _json_dict(payload.get(field))
        payload[field] = {key: raw[key] for key in sorted(allowed) if key in raw}
    return PaperEventRead.model_validate(payload)


async def get_or_raise_account(
    session: AsyncSession,
    *,
    user_id: int,
    for_update: bool = False,
    require_active: bool = False,
) -> dict[str, Any]:
    account = await repository.get_account(
        session, owner_user_id=user_id, for_update=for_update
    )
    if account is None:
        raise TradingNotFoundError("paper account not found")
    if account.get("ownership_scope") != "PERSONAL" or account.get("paper_only") is not True:
        raise TradingPaperOnlyError("paper account violates PERSONAL/PAPER_ONLY contract")
    if require_active and account.get("status") != "ACTIVE":
        raise TradingConflictError("paper account is not active")
    return account


async def create_paper_account(
    session: AsyncSession, *, user_id: int, payload: PaperAccountCreate
) -> PaperAccountRead:
    _paper_only()
    await repository.require_schema(session)
    if payload.ownership_scope != "PERSONAL" or payload.paper_only is not True:
        raise TradingPaperOnlyError("only PERSONAL PAPER_ONLY accounts are supported")
    try:
        account = await repository.create_account(
            session,
            owner_user_id=user_id,
            quote_asset=payload.quote_asset,
            initial_virtual_balance=payload.initial_virtual_balance,
            ruleset_version=RULES.ruleset_version,
        )
        if account.pop("_created", False):
            await repository.insert_event(
                session,
                values={
                    "owner_user_id": user_id,
                    "paper_account_id": account["id"],
                    "event_type": "PAPER_ACCOUNT_CREATED",
                    "signal_id": None,
                    "prediction_id": None,
                    "order_id": None,
                    "position_id": None,
                    "symbol": None,
                    "event_payload": {
                        "quote_asset": account["quote_asset"],
                        "initial_virtual_balance": str(account["initial_virtual_balance"]),
                        "paper_only": True,
                    },
                    "decision_context": {"ownership_scope": "PERSONAL"},
                    "risk_context": {"real_trading_capital": "0.00"},
                    "correlation_id": str(uuid.uuid4()),
                },
            )
        await session.commit()
        return _account_read(account)
    except Exception:
        await session.rollback()
        raise


async def get_paper_account(session: AsyncSession, *, user_id: int) -> PaperAccountRead:
    _paper_only()
    await repository.require_schema(session)
    return _account_read(await get_or_raise_account(session, user_id=user_id))


async def get_risk_budget(
    session: AsyncSession, *, user_id: int, household_id: int
) -> TradingRiskBudgetRead:
    _paper_only()
    await repository.require_schema(session)
    return await current_trading_risk_budget(
        session, household_id=household_id, user_id=user_id
    )


def _prediction_from_signal(signal: Mapping[str, Any]) -> PredictionResult:
    reason = _json_dict(signal.get("reason"))
    prediction_id = signal.get("prediction_id")
    feature_version = signal.get("feature_version")
    target_name = signal.get("target_name")
    model_version = signal.get("model_version")
    candle_id = signal.get("candle_id")
    probability_tp = reason.get("probability_take_profit")
    probability_sl = reason.get("probability_stop_loss")
    probability_neutral = reason.get("probability_neutral")
    confidence = signal.get("probability") or reason.get("confidence")
    required = {
        "prediction_id": prediction_id,
        "feature_version": feature_version,
        "target_name": target_name,
        "model_version": model_version,
        "candle_id": candle_id,
        "probability_take_profit": probability_tp,
        "probability_stop_loss": probability_sl,
        "probability_neutral": probability_neutral,
        "confidence": confidence,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        raise TradingValidationError(
            "signal is research-only and lacks operational fields: " + ", ".join(missing)
        )
    return PredictionResult(
        prediction_id=str(prediction_id),
        symbol=str(signal["symbol"]),
        interval=str(signal["interval"]),
        target_name=str(target_name),
        candle_id=int(candle_id),
        open_time=signal["signal_time"],
        model_name=str(reason.get("model_name") or "unknown"),
        artifact_dir=Path("."),
        predicted_class=1,
        probability_stop_loss=float(probability_sl),
        probability_neutral=float(probability_neutral),
        probability_take_profit=float(probability_tp),
        confidence=float(confidence),
        confidence_level=str(reason.get("confidence_level") or "MODEL_OUTPUT"),
        decision=BUY_CANDIDATE,
        prediction_engine_version=str(
            reason.get("prediction_engine_version") or "prediction-v2"
        ),
        model_version=str(model_version),
        feature_version=str(feature_version),
        risk_score=float(reason.get("risk_score") or probability_sl),
        expected_return=float(reason.get("expected_return") or 0),
        expected_drawdown=float(reason.get("expected_drawdown") or 0),
        loaded_manifest={},
        reason={**reason, "paper_only": True},
    )


def _active_registry_model(reason: Mapping[str, Any]):
    model_id = reason.get("model_id")
    if not model_id:
        raise TradingValidationError("signal has no promoted model identity")
    try:
        entry = get_registry().get(str(model_id))
    except RuntimeError as exc:
        raise TradingDataUnavailableError("Trading model registry is unavailable") from exc
    if entry is None or entry.promotion_status != "PAPER_ACTIVE":
        raise TradingValidationError("signal model is not PAPER_ACTIVE")
    return entry


async def _portfolio_for_risk(
    session: AsyncSession, *, account: Mapping[str, Any], user_id: int
) -> PortfolioState:
    positions, _ = await repository.list_positions(
        session, owner_user_id=user_id, status="OPEN", limit=100, offset=0
    )
    history = await repository.paper_risk_history(
        session,
        paper_account_id=int(account["id"]),
        owner_user_id=user_id,
    )
    executed_keys = {
        (
            str(item["symbol"]),
            str(item["interval"]),
            int(item["candle_id"]),
            str(item["model_version"]),
        )
        for item in history["executed"]
    }
    last_trade_index: dict[str, int] = {}
    for item in history["executed"]:
        symbol = str(item["symbol"])
        last_trade_index[symbol] = max(
            last_trade_index.get(symbol, -1), int(item["candle_id"])
        )
    return PortfolioState(
        initial_capital=float(account["initial_virtual_balance"]),
        cash=float(account["cash"]),
        equity=float(account["equity"]),
        positions=[SimpleNamespace(status="OPEN") for _ in positions],
        peak_equity=float(account["peak_equity"]),
        max_drawdown=float(account["max_drawdown"]),
        daily_results={item["trading_day"]: float(item["pnl"]) for item in history["daily"]},
        last_trade_index=last_trade_index,
        executed_keys=executed_keys,
    )


async def create_order(
    session: AsyncSession,
    *,
    user_id: int,
    household_id: int,
    payload: PaperOrderCreate,
) -> PaperOrderRead:
    _paper_only()
    await repository.require_schema(session)
    if payload.paper_only is not True:
        raise TradingPaperOnlyError("PAPER_ONLY mode is server controlled")
    symbol = payload.symbol.upper()
    if payload.market != RULES.supported_market or symbol not in RULES.supported_symbols:
        raise TradingValidationError("unsupported paper market or symbol")
    if payload.interval not in RULES.supported_intervals:
        raise TradingValidationError("unsupported paper interval")
    if payload.side not in RULES.supported_open_sides:
        raise TradingValidationError("Paper Trading V2 currently opens long positions only")
    if payload.signal_id is None:
        raise TradingValidationError("a current validated paper signal is required")

    correlation_id = str(uuid.uuid4())
    request_payload = payload.model_dump(mode="json")
    request_fingerprint = _canonical_hash(request_payload)
    try:
        account = await get_or_raise_account(
            session, user_id=user_id, for_update=True, require_active=True
        )
        existing = await repository.get_order_by_idempotency(
            session,
            paper_account_id=int(account["id"]),
            owner_user_id=user_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            if existing.get("request_fingerprint") != request_fingerprint:
                raise TradingConflictError(
                    "idempotency key was already used for a different request"
                )
            await session.rollback()
            return _order_read(existing)

        signal = await repository.get_signal(session, signal_id=payload.signal_id)
        if signal is None:
            raise TradingValidationError("signal not found")
        if str(signal.get("symbol")).upper() != symbol or signal.get("interval") != payload.interval:
            raise TradingValidationError("signal does not match requested asset")
        if signal.get("paper_only") is not True:
            raise TradingPaperOnlyError("signal is not PAPER_ONLY")
        if signal.get("guardrail_status") != "APPROVED":
            raise TradingValidationError("signal guardrails are not approved")
        expires_at = signal.get("freshness_expires_at")
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise TradingValidationError("signal is stale")
        reason = _json_dict(signal.get("reason"))
        registry_model = _active_registry_model(reason)
        if registry_model.version != str(signal.get("model_version")):
            raise TradingValidationError("signal model version does not match registry")

        prediction = _prediction_from_signal(signal)
        risk = PaperRiskManager(DEFAULT_CONFIG)
        risk.validate_prediction(prediction)
        portfolio = await _portfolio_for_risk(session, account=account, user_id=user_id)
        allowed, risk_reason = risk.can_open(
            portfolio=portfolio,
            prediction=prediction,
            candle_index=int(prediction.candle_id),
        )
        if not allowed:
            raise TradingValidationError(f"paper risk guard blocked order: {risk_reason}")

        budget = await current_trading_risk_budget(
            session, household_id=household_id, user_id=user_id
        )
        candle = await repository.latest_reference_price(
            session,
            symbol=symbol,
            interval=payload.interval,
            max_age_seconds=RULES.reference_price_max_age_seconds,
        )
        if candle is None or _decimal(candle.get("close")) <= 0:
            raise TradingDataUnavailableError("fresh Trading reference price is unavailable")

        executor = PaperTradingExecutor(DEFAULT_CONFIG)
        reference_price = _decimal(candle["close"])
        entry_price = Decimal(str(executor.entry_price(float(reference_price)))).quantize(
            MONEY_QUANT
        )
        target_rules = parse_target_name(prediction.target_name)
        stop_price = (
            entry_price * Decimal(str(1 - target_rules.stop_loss_pct))
        ).quantize(MONEY_QUANT)
        target_price = (
            entry_price * Decimal(str(1 + target_rules.take_profit_pct))
        ).quantize(MONEY_QUANT)
        max_notional = Decimal(str(risk.position_notional(portfolio))).quantize(
            MONEY_QUANT, rounding=ROUND_DOWN
        )
        requested_notional = (
            _decimal(payload.notional)
            if payload.notional is not None
            else (_decimal(payload.quantity) * entry_price)
        )
        if requested_notional <= 0 or requested_notional > max_notional:
            raise TradingValidationError(
                f"paper order exceeds the simulation risk limit ({max_notional})"
            )
        quantity = (
            _decimal(payload.quantity)
            if payload.quantity is not None
            else (requested_notional / entry_price).quantize(MONEY_QUANT, rounding=ROUND_DOWN)
        )
        entry_fee = Decimal(str(executor.fee(float(requested_notional)))).quantize(
            MONEY_QUANT
        )
        if requested_notional + entry_fee > _decimal(account.get("cash")):
            raise TradingValidationError("insufficient virtual balance for paper order")
        limit_can_fill = (
            payload.order_type == "MARKET"
            or (payload.limit_price is not None and entry_price <= payload.limit_price)
        )
        status = "FILLED" if limit_can_fill else "PENDING"
        risk_snapshot = {
            "ruleset_version": RULES.ruleset_version,
            "paper_engine_version": DEFAULT_CONFIG.engine_version,
            "max_notional": str(max_notional),
            "entry_fee": str(entry_fee),
            "risk_reason": risk_reason,
            "real_trading_allowed": False,
            "real_trading_capital": "0.00",
            "paper_only": True,
            "reference_price_max_age_seconds": RULES.reference_price_max_age_seconds,
        }
        order = await repository.insert_order(
            session,
            values={
                "paper_account_id": account["id"],
                "owner_user_id": user_id,
                "idempotency_key": payload.idempotency_key,
                "request_fingerprint": request_fingerprint,
                "correlation_id": correlation_id,
                "signal_id": payload.signal_id,
                "prediction_id": prediction.prediction_id,
                "symbol": symbol,
                "market": payload.market,
                "interval": payload.interval,
                "side": payload.side,
                "order_type": payload.order_type,
                "quantity": quantity,
                "notional": requested_notional,
                "reference_price": entry_price,
                "limit_price": payload.limit_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "status": status,
                "model_version": prediction.model_version,
                "feature_version": prediction.feature_version,
                "target_version": str(prediction.target_name).split("_", 1)[0],
                "risk_decision": "PAPER_APPROVED",
                "risk_snapshot": risk_snapshot,
                "financial_fingerprints": budget.context_fingerprints,
                "filled_at": datetime.now(timezone.utc) if status == "FILLED" else None,
                "fee_paid": entry_fee if status == "FILLED" else Decimal("0"),
            },
        )
        await repository.insert_event(
            session,
            values={
                "owner_user_id": user_id,
                "paper_account_id": account["id"],
                "event_type": "PAPER_RISK_CHECK_APPROVED",
                "signal_id": payload.signal_id,
                "prediction_id": prediction.prediction_id,
                "order_id": order["id"],
                "position_id": None,
                "symbol": symbol,
                "event_payload": {"order_status": status, "paper_only": True},
                "decision_context": {
                    "model_version": prediction.model_version,
                    "feature_version": prediction.feature_version,
                    "target_name": prediction.target_name,
                },
                "risk_context": risk_snapshot,
                "correlation_id": correlation_id,
            },
        )
        if status == "FILLED":
            await repository.update_account_after_open(
                session,
                account_id=int(account["id"]),
                owner_user_id=user_id,
                debit=requested_notional + entry_fee,
                entry_fee=entry_fee,
            )
            position = await repository.insert_position(
                session,
                values={
                    "paper_account_id": account["id"],
                    "owner_user_id": user_id,
                    "symbol": symbol,
                    "market": payload.market,
                    "interval": payload.interval,
                    "side": "LONG",
                    "quantity": quantity,
                    "average_entry_price": entry_price,
                    "current_reference_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "opening_order_id": order["id"],
                    "entry_fee": entry_fee,
                },
            )
            await repository.insert_event(
                session,
                values={
                    "owner_user_id": user_id,
                    "paper_account_id": account["id"],
                    "event_type": "PAPER_POSITION_OPENED",
                    "signal_id": payload.signal_id,
                    "prediction_id": prediction.prediction_id,
                    "order_id": order["id"],
                    "position_id": position["id"],
                    "symbol": symbol,
                    "event_payload": {
                        "quantity": str(quantity),
                        "entry_price": str(entry_price),
                        "entry_fee": str(entry_fee),
                        "paper_only": True,
                    },
                    "decision_context": {"signal_id": payload.signal_id},
                    "risk_context": risk_snapshot,
                    "correlation_id": correlation_id,
                },
            )
        await session.commit()
        return _order_read(order)
    except IntegrityError as exc:
        await session.rollback()
        account = await repository.get_account(session, owner_user_id=user_id)
        if account is not None:
            existing = await repository.get_order_by_idempotency(
                session,
                paper_account_id=int(account["id"]),
                owner_user_id=user_id,
                idempotency_key=payload.idempotency_key,
            )
            if existing is not None and existing.get("request_fingerprint") == request_fingerprint:
                return _order_read(existing)
        raise TradingConflictError("paper order conflicts with an existing operation") from exc
    except Exception:
        await session.rollback()
        raise


async def cancel_order(
    session: AsyncSession,
    *,
    user_id: int,
    order_id: int,
    payload: IdempotentAction,
) -> PaperOrderRead:
    _paper_only()
    await repository.require_schema(session)
    correlation_id = str(uuid.uuid4())
    try:
        account = await get_or_raise_account(session, user_id=user_id, for_update=True)
        order = await repository.get_order(
            session, order_id=order_id, owner_user_id=user_id, for_update=True
        )
        if order is None:
            raise TradingNotFoundError("paper order not found")
        if order["status"] == "CANCELLED":
            await session.rollback()
            return _order_read(order)
        if order["status"] != "PENDING":
            raise TradingConflictError("only pending paper orders can be cancelled")
        cancelled = await repository.cancel_order(
            session, order_id=order_id, owner_user_id=user_id
        )
        await repository.insert_event(
            session,
            values={
                "owner_user_id": user_id,
                "paper_account_id": account["id"],
                "event_type": "PAPER_ORDER_CANCELLED",
                "signal_id": order.get("signal_id"),
                "prediction_id": order.get("prediction_id"),
                "order_id": order_id,
                "position_id": None,
                "symbol": order.get("symbol"),
                "event_payload": {
                    "status": "CANCELLED",
                    "paper_only": True,
                },
                "decision_context": {},
                "risk_context": {},
                "correlation_id": correlation_id,
            },
        )
        await session.commit()
        return _order_read(cancelled)
    except Exception:
        await session.rollback()
        raise


async def close_position(
    session: AsyncSession,
    *,
    user_id: int,
    position_id: int,
    payload: IdempotentAction,
) -> PaperPositionRead:
    _paper_only()
    await repository.require_schema(session)
    correlation_id = str(uuid.uuid4())
    request_fingerprint = _canonical_hash(
        {
            "action": "CLOSE_POSITION",
            "position_id": position_id,
            "idempotency_key": payload.idempotency_key,
            "paper_only": True,
        }
    )
    try:
        account = await get_or_raise_account(
            session, user_id=user_id, for_update=True, require_active=True
        )
        existing_close = await repository.get_order_by_idempotency(
            session,
            paper_account_id=int(account["id"]),
            owner_user_id=user_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing_close is not None:
            if existing_close.get("request_fingerprint") != request_fingerprint:
                raise TradingConflictError(
                    "idempotency key was already used for a different request"
                )
            position = await repository.get_position(
                session, position_id=position_id, owner_user_id=user_id
            )
            if position is None:
                raise TradingNotFoundError("paper position not found")
            await session.rollback()
            return _position_read(position)
        position = await repository.get_position(
            session,
            position_id=position_id,
            owner_user_id=user_id,
            for_update=True,
        )
        if position is None:
            raise TradingNotFoundError("paper position not found")
        if position["status"] != "OPEN":
            raise TradingConflictError("paper position is not open")
        candle = await repository.latest_reference_price(
            session,
            symbol=position["symbol"],
            interval=position["interval"],
            max_age_seconds=RULES.reference_price_max_age_seconds,
        )
        if candle is None or _decimal(candle.get("close")) <= 0:
            raise TradingDataUnavailableError("fresh Trading reference price is unavailable")
        executor = PaperTradingExecutor(DEFAULT_CONFIG)
        exit_price = Decimal(
            str(executor.exit_price(float(_decimal(candle["close"]))))
        ).quantize(MONEY_QUANT)
        quantity = _decimal(position["quantity"])
        exit_notional = (exit_price * quantity).quantize(MONEY_QUANT)
        exit_fee = Decimal(str(executor.fee(float(exit_notional)))).quantize(MONEY_QUANT)
        entry_fee = _decimal(position.get("entry_fee"))
        realized_pnl = (
            (exit_price - _decimal(position["average_entry_price"])) * quantity
            - entry_fee
            - exit_fee
        ).quantize(MONEY_QUANT)
        order = await repository.insert_order(
            session,
            values={
                "paper_account_id": account["id"],
                "owner_user_id": user_id,
                "idempotency_key": payload.idempotency_key,
                "request_fingerprint": request_fingerprint,
                "correlation_id": correlation_id,
                "signal_id": None,
                "prediction_id": None,
                "symbol": position["symbol"],
                "market": position["market"],
                "interval": position["interval"],
                "side": "SELL",
                "order_type": "MARKET",
                "quantity": quantity,
                "notional": exit_notional,
                "reference_price": exit_price,
                "limit_price": None,
                "stop_price": position.get("stop_price"),
                "target_price": position.get("target_price"),
                "status": "FILLED",
                "model_version": None,
                "feature_version": None,
                "target_version": None,
                "risk_decision": "PAPER_CLOSE_APPROVED",
                "risk_snapshot": {
                    "paper_only": True,
                    "exit_fee": str(exit_fee),
                    "real_trading_capital": "0.00",
                },
                "financial_fingerprints": {},
                "filled_at": datetime.now(timezone.utc),
                "fee_paid": exit_fee,
            },
        )
        closed = await repository.close_position(
            session,
            position_id=position_id,
            owner_user_id=user_id,
            closing_order_id=int(order["id"]),
            exit_price=exit_price,
            realized_pnl=realized_pnl,
        )
        await repository.update_account_after_close(
            session,
            account_id=int(account["id"]),
            owner_user_id=user_id,
            proceeds_after_fee=exit_notional - exit_fee,
            realized_pnl=realized_pnl,
        )
        await repository.insert_event(
            session,
            values={
                "owner_user_id": user_id,
                "paper_account_id": account["id"],
                "event_type": "PAPER_POSITION_CLOSED",
                "signal_id": None,
                "prediction_id": None,
                "order_id": order["id"],
                "position_id": position_id,
                "symbol": position["symbol"],
                "event_payload": {
                    "exit_price": str(exit_price),
                    "realized_pnl": str(realized_pnl),
                    "fees": str(entry_fee + exit_fee),
                    "paper_only": True,
                },
                "decision_context": {"reason": "USER_REQUESTED_PAPER_CLOSE"},
                "risk_context": {"real_trading_capital": "0.00"},
                "correlation_id": correlation_id,
            },
        )
        await session.commit()
        return _position_read(closed)
    except IntegrityError as exc:
        await session.rollback()
        account = await repository.get_account(session, owner_user_id=user_id)
        if account is not None:
            existing = await repository.get_order_by_idempotency(
                session,
                paper_account_id=int(account["id"]),
                owner_user_id=user_id,
                idempotency_key=payload.idempotency_key,
            )
            if existing is not None and existing.get("request_fingerprint") == request_fingerprint:
                position = await repository.get_position(
                    session, position_id=position_id, owner_user_id=user_id
                )
                if position is not None:
                    return _position_read(position)
        raise TradingConflictError("concurrent paper position operation rejected") from exc
    except Exception:
        await session.rollback()
        raise


async def list_paper_orders(
    session: AsyncSession,
    *,
    user_id: int,
    status: str | None,
    limit: int,
    offset: int,
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    items, total = await repository.list_orders(
        session, owner_user_id=user_id, status=status, limit=limit, offset=offset
    )
    return TradingListResponse(
        items=[_order_read(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


async def list_paper_positions(
    session: AsyncSession,
    *,
    user_id: int,
    status: str | None,
    limit: int,
    offset: int,
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    items, total = await repository.list_positions(
        session, owner_user_id=user_id, status=status, limit=limit, offset=offset
    )
    return TradingListResponse(
        items=[_position_read(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


async def list_paper_events(
    session: AsyncSession, *, user_id: int, limit: int, offset: int
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    items, total = await repository.list_events(
        session, owner_user_id=user_id, limit=limit, offset=offset
    )
    return TradingListResponse(
        items=[_event_read(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def _public_signal_reason(value: Any) -> dict[str, Any]:
    raw = _json_dict(value)
    allowed = {
        "paper_only",
        "model_id",
        "model_name",
        "prediction_engine_version",
        "confidence",
        "confidence_level",
        "probability_take_profit",
        "probability_stop_loss",
        "probability_neutral",
        "risk_score",
        "expected_return",
        "expected_drawdown",
        "decision",
        "decision_reason",
        "fresh",
        "freshness_policy",
        "continuous_scheduler_enabled",
        "reasons",
    }
    projected = {key: raw[key] for key in sorted(allowed) if key in raw}
    reasons = projected.get("reasons")
    if isinstance(reasons, list):
        sensitive_markers = ("password", "secret", "token", "api_key", "\\users\\", "/home/")
        projected["reasons"] = [
            item[:300]
            for item in reasons[:10]
            if isinstance(item, str)
            and not any(marker in item.casefold() for marker in sensitive_markers)
        ]
    elif "reasons" in projected:
        projected["reasons"] = []
    return projected


def _signal_read(row: Mapping[str, Any]) -> TradingSignalRead:
    return TradingSignalRead(
        id=row["id"],
        symbol=row["symbol"],
        interval=row["interval"],
        signal_time=row["signal_time"],
        model_version=row["model_version"],
        side=row["side"],
        probability=row.get("probability"),
        score=row.get("score"),
        reason=_public_signal_reason(row.get("reason")),
        created_at=row["created_at"],
    )


async def list_signals(
    session: AsyncSession,
    *,
    symbol: str | None,
    limit: int,
    offset: int,
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    items, total = await repository.list_signals(
        session,
        opportunities_only=False,
        symbol=symbol.upper() if symbol else None,
        limit=limit,
        offset=offset,
    )
    return TradingListResponse(
        items=[_signal_read(item).model_dump() for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


async def list_opportunities(
    session: AsyncSession,
    *,
    symbol: str | None,
    limit: int,
    offset: int,
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    try:
        active_models = get_registry().active()
    except RuntimeError as exc:
        raise TradingDataUnavailableError(
            "Trading model registry is unavailable"
        ) from exc
    rows, total = await repository.list_signals(
        session,
        opportunities_only=True,
        symbol=symbol.upper() if symbol else None,
        limit=limit,
        offset=offset,
        active_models=[(item.model_id, item.version) for item in active_models],
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        reason = _public_signal_reason(row.get("reason"))
        try:
            registry_model = _active_registry_model(reason)
        except (TradingValidationError, TradingDataUnavailableError):
            continue
        if registry_model.version != str(row.get("model_version")):
            continue
        opportunity = TradingOpportunityRead(
            signal_id=row["id"],
            symbol=row["symbol"],
            interval=row["interval"],
            signal_time=row["signal_time"],
            freshness="FRESH",
            side=row["side"],
            confidence=row.get("probability"),
            score=row.get("score"),
            reference_price=row.get("reference_price"),
            stop_price=row.get("stop_price"),
            target_price=row.get("target_price"),
            model_version=row["model_version"],
            feature_version=row.get("feature_version"),
            target_version=row.get("target_version"),
            guardrail_status=row.get("guardrail_status") or "UNKNOWN",
            reasons=[str(value) for value in reason.get("reasons", [])][:10],
        )
        items.append(opportunity.model_dump())
    return TradingListResponse(items=items, total=total, limit=limit, offset=offset)


def _backtest_read(row: Mapping[str, Any]) -> TradingBacktestRead:
    raw_parameters = _json_dict(row.get("parameters"))
    raw_metrics = _json_dict(row.get("metrics"))
    parameter_keys = {
        "model",
        "model_name",
        "symbol",
        "interval",
        "period_start",
        "period_end",
        "feature_version",
        "target_version",
        "target_name",
        "dataset_version",
        "fee_bps",
        "slippage_bps",
        "spread_bps",
        "threshold",
        "horizon_candles",
    }
    metric_keys = {
        "trades",
        "total_trades",
        "gross_return",
        "gross_total_return",
        "net_return",
        "total_return",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "sharpe",
        "sharpe_ratio",
        "fees",
        "total_fees",
        "slippage",
        "total_slippage",
        "spread",
        "total_spread",
    }
    parameters = {
        key: raw_parameters[key]
        for key in sorted(parameter_keys)
        if key in raw_parameters
    }
    metrics = {
        key: raw_metrics[key] for key in sorted(metric_keys) if key in raw_metrics
    }
    return TradingBacktestRead(
        id=str(row["id"]),
        name=str(row["name"]),
        model=parameters.get("model") or parameters.get("model_name"),
        symbol=parameters.get("symbol"),
        interval=parameters.get("interval"),
        period_start=parameters.get("period_start"),
        period_end=parameters.get("period_end"),
        trades=metrics.get("trades") or metrics.get("total_trades"),
        gross_return=metrics.get("gross_return") or metrics.get("gross_total_return"),
        net_return=metrics.get("net_return") or metrics.get("total_return"),
        win_rate=metrics.get("win_rate"),
        profit_factor=metrics.get("profit_factor"),
        max_drawdown=metrics.get("max_drawdown"),
        sharpe=metrics.get("sharpe") or metrics.get("sharpe_ratio"),
        fees=metrics.get("fees") or metrics.get("total_fees"),
        slippage=metrics.get("slippage") or metrics.get("total_slippage"),
        spread=metrics.get("spread") or metrics.get("total_spread"),
        costs_modeled=any(
            key in metrics
            for key in ("fees", "total_fees", "slippage", "total_slippage", "spread")
        ),
        status=str(row.get("status") or "UNKNOWN"),
        parameters=parameters,
        metrics=metrics,
    )


async def list_backtests(
    session: AsyncSession, *, limit: int, offset: int
) -> TradingListResponse:
    _paper_only()
    await repository.require_schema(session)
    rows, total = await repository.list_backtest_rows(
        session, limit=limit, offset=offset
    )
    valid = [_backtest_read(row).model_dump() for row in rows]
    return TradingListResponse(items=valid, total=total, limit=limit, offset=offset)


async def get_backtest(session: AsyncSession, *, backtest_id: int) -> TradingBacktestRead:
    _paper_only()
    await repository.require_schema(session)
    row = await repository.get_backtest_row(session, backtest_id=backtest_id)
    if row is None or not row.get("metrics"):
        raise TradingNotFoundError("backtest not found")
    return _backtest_read(row)


def _model_read(entry) -> TradingModelRead:
    return TradingModelRead.model_validate(entry.public_dict())


async def list_models(*, limit: int, offset: int) -> TradingListResponse:
    _paper_only()
    try:
        entries = get_registry().list()
    except RuntimeError as exc:
        raise TradingDataUnavailableError("Trading model registry is unavailable") from exc
    page = entries[offset : offset + limit]
    return TradingListResponse(
        items=[_model_read(entry).model_dump() for entry in page],
        total=len(entries),
        limit=limit,
        offset=offset,
    )


async def get_model(*, model_id: str) -> TradingModelRead:
    _paper_only()
    try:
        entry = get_registry().get(model_id)
    except RuntimeError as exc:
        raise TradingDataUnavailableError("Trading model registry is unavailable") from exc
    if entry is None:
        raise TradingNotFoundError("Trading model not found")
    return _model_read(entry)


async def overview(
    session: AsyncSession, *, user_id: int, household_id: int
) -> TradingOverviewRead:
    _paper_only()
    await repository.require_schema(session)
    budget = await current_trading_risk_budget(
        session, household_id=household_id, user_id=user_id
    )
    account_row = await repository.get_account(session, owner_user_id=user_id)
    account = _account_read(account_row) if account_row else None
    counts = {"opportunities": 0, "open_positions": 0, "pending_orders": 0}
    if account_row:
        counts.update(await repository.account_counts(session, owner_user_id=user_id))
    try:
        opportunities = await list_opportunities(
            session, symbol=None, limit=1, offset=0
        )
        counts["opportunities"] = opportunities.total
    except TradingDataUnavailableError:
        # Account/risk information remains useful when the independently
        # managed model registry is absent or invalid.  Model health below
        # exposes that degraded state without fabricating opportunities.
        counts["opportunities"] = 0
    performance = {
        "realized_pnl": account.realized_pnl if account else Decimal("0"),
        "unrealized_pnl": account.unrealized_pnl if account else Decimal("0"),
        "equity": account.equity if account else Decimal("0"),
        "drawdown": account.max_drawdown if account else Decimal("0"),
    }
    try:
        model_health = get_registry().health()
    except RuntimeError:
        model_health = {
            "status": "REGISTRY_UNAVAILABLE",
            "total": 0,
            "active": 0,
            "paper_trading_ready": False,
        }
    return TradingOverviewRead(
        product_status=(
            "PAPER_READY"
            if model_health.get("paper_trading_ready")
            else "RESEARCH_NOT_PAPER_READY"
        ),
        risk_budget=budget,
        paper_account=account,
        counts=counts,
        performance=performance,
        models=model_health,
    )


async def health(session: AsyncSession) -> TradingHealthRead:
    _paper_only()
    version = await repository.schema_version(session)
    from backend.trading.storage.migrate import LATEST_TRADING_SCHEMA_VERSION

    compatible = version == LATEST_TRADING_SCHEMA_VERSION
    warnings = []
    if not compatible:
        warnings.append("TRADING_SCHEMA_NOT_READY")
    try:
        model_health = get_registry().health()
    except RuntimeError:
        model_health = {
            "status": "REGISTRY_UNAVAILABLE",
            "total": 0,
            "active": 0,
            "paper_trading_ready": False,
        }
        warnings.append("MODEL_REGISTRY_UNAVAILABLE")
    paper_ready = bool(model_health.get("paper_trading_ready"))
    if not paper_ready:
        warnings.append("VALIDATION_V2_NOT_PAPER_READY")
    return TradingHealthRead(
        status="attention" if warnings else "healthy",
        schema_version=version,
        schema_compatible=compatible,
        research_data_ready=False,
        model_registry_ready=model_health.get("status") != "REGISTRY_UNAVAILABLE",
        paper_trading_ready=paper_ready,
        warnings=warnings,
    )

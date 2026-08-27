from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.logging import get_logger
from backend.app.core.trace import decision_trace_context
from backend.app.intelligence.services.budget_advisor_service import build_explained_budget_recommendations
from backend.app.investment_alerts.evaluator import (
    Observation,
    build_evaluation_key,
    cooldown_allows,
    detect_relevant_events,
)
from backend.app.investment_alerts.models import (
    InvestmentAlertState,
    InvestmentAlertSubscription,
)
from backend.app.investment_alerts.repository import (
    DuplicateSubscriptionError,
    count_active_subscriptions,
    create_subscription_with_state,
    delete_subscription,
    get_alert_metrics,
    get_decision_by_id,
    get_owned_source_decision,
    get_owned_subscription,
    get_subscription_state_for_update,
    increment_state_error,
    insert_alert_if_absent,
    latest_alerts_by_type,
    list_active_subscription_ids,
    list_owned_subscriptions,
    lock_user_subscription_quota,
    save_subscription,
)
from backend.app.investment_alerts.rules import (
    ALERT_RULE_VERSION,
    DELIVERY_CHANNEL_IN_APP,
    MAX_ACTIVE_SUBSCRIPTIONS_PER_USER,
    MAX_ALERTS_PER_CYCLE,
    MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION,
    MAX_SUBSCRIPTIONS_PER_CYCLE,
    MONITORING_RECOMMENDATION_LIMIT,
)
from backend.app.investment_alerts.schemas import SubscriptionCreate, SubscriptionUpdate
from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_decisions.service import (
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_SUCCESS,
    build_decision_audit,
    canonical_uuid,
    normalize_asset_filter,
    parse_decision_id,
    persist_decision_audit,
    persist_decision_audit_fail_open,
    sanitize_snapshot,
)


logger = get_logger(__name__)
UTC = timezone.utc
AUTOMATION_SOURCE = "INVESTMENT_ALERT_AUTOMATION"


class SubscriptionNotFoundError(LookupError):
    pass


class SubscriptionSourceError(ValueError):
    pass


class SubscriptionLimitError(ValueError):
    pass


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _focused_payload(payload: dict[str, Any], asset: str) -> tuple[dict[str, Any], bool]:
    candidates: list[dict[str, Any]] = []
    best = payload.get("best_recommendation")
    if isinstance(best, dict):
        candidates.append(best)
    alternatives = payload.get("alternatives")
    if isinstance(alternatives, list):
        candidates.extend(item for item in alternatives if isinstance(item, dict))
    selected = next(
        (item for item in candidates if str(item.get("ticker", "")).strip().upper() == asset),
        None,
    )
    if selected is None:
        return {**payload, "best_recommendation": None, "alternatives": candidates[:19]}, False
    return {
        **payload,
        "best_recommendation": selected,
        "alternatives": [item for item in candidates if item is not selected][:19],
    }, True


def observation_from_decision(decision: InvestmentDecisionAudit) -> Observation:
    return Observation.from_values(
        decision_id=decision.decision_id,
        action=decision.recommendation,
        score=decision.recommendation_score,
        confidence=decision.confidence,
        risk_level=decision.risk_level,
        trend=decision.trend,
        observed_at=decision.created_at,
    )


def observation_from_state(state: InvestmentAlertState) -> Observation:
    return Observation.from_values(
        decision_id=state.last_decision_id,
        action=state.last_action,
        score=state.last_score,
        confidence=state.last_confidence,
        risk_level=state.last_risk_level,
        trend=state.last_trend,
        observed_at=state.last_checked_at,
    )


def _deterministic_trace_ids(evaluation_key: str) -> tuple[str, str]:
    return (
        str(uuid5(NAMESPACE_URL, f"vinanceos:investment-alert:decision:{evaluation_key}")),
        str(uuid5(NAMESPACE_URL, f"vinanceos:investment-alert:correlation:{evaluation_key}")),
    )


async def create_monitoring_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    payload: SubscriptionCreate,
) -> InvestmentAlertSubscription:
    asset = normalize_asset_filter(payload.asset)
    assert asset is not None
    source_id = parse_decision_id(payload.source_decision_id)
    if source_id is None:
        raise SubscriptionSourceError("decisão de origem inválida")

    await lock_user_subscription_quota(session, user_id=user_id)
    if await count_active_subscriptions(session, user_id=user_id) >= MAX_ACTIVE_SUBSCRIPTIONS_PER_USER:
        raise SubscriptionLimitError("limite de monitoramentos ativos atingido")
    source = await get_owned_source_decision(
        session,
        user_id=user_id,
        asset=asset,
        decision_id=source_id,
    )
    if source is None or not source.market or source.budget <= 0 or not source.investor_profile:
        raise SubscriptionSourceError(
            "gere uma decisão auditada para este ativo antes de ativar o monitoramento"
        )
    request_parameters = source.request_parameters if isinstance(source.request_parameters, dict) else {}
    subscription = InvestmentAlertSubscription(
        user_id=user_id,
        asset=asset,
        market=str(source.market),
        budget=source.budget,
        investor_profile=str(source.investor_profile),
        include_warnings=_as_bool(request_parameters.get("include_warnings"), False),
        trend_filter=(str(request_parameters["trend_filter"])[:32] if request_parameters.get("trend_filter") else None),
        source_decision_id=source.decision_id,
        enabled=True,
        alert_on_action_change=payload.alert_on_action_change,
        alert_on_score_change=payload.alert_on_score_change,
        alert_on_confidence_change=payload.alert_on_confidence_change,
        alert_on_risk_change=payload.alert_on_risk_change,
        alert_on_new_opportunity=payload.alert_on_new_opportunity,
        minimum_score_delta=payload.minimum_score_delta,
        minimum_confidence_delta=payload.minimum_confidence_delta,
        cooldown_minutes=payload.cooldown_minutes,
        rule_version=ALERT_RULE_VERSION,
    )
    initial = observation_from_decision(source)
    state = InvestmentAlertState(
        subscription_id=0,
        user_id=user_id,
        asset=asset,
        last_decision_id=initial.decision_id,
        last_action=initial.action,
        last_score=initial.score,
        last_confidence=initial.confidence,
        last_risk_level=initial.risk_level,
        last_trend=initial.trend,
        last_checked_at=source.created_at,
    )
    created = await create_subscription_with_state(
        session,
        subscription=subscription,
        state=state,
    )
    logger.info(
        "investment_alert.subscription_created",
        extra={
            "event": "investment_alert.subscription_created",
            "user_id": user_id,
            "asset": asset,
            "subscription_id": created.id,
            "decision_id": source.decision_id,
            "status": "ACTIVE",
        },
    )
    return created


async def list_monitoring_subscriptions(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    items = await list_owned_subscriptions(session, user_id=user_id)
    return {
        "items": items,
        "total": len(items),
        "active": sum(1 for item in items if item.enabled),
        "limit": MAX_ACTIVE_SUBSCRIPTIONS_PER_USER,
    }


async def update_monitoring_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
    payload: SubscriptionUpdate,
) -> InvestmentAlertSubscription:
    subscription = await get_owned_subscription(
        session, user_id=user_id, subscription_id=subscription_id
    )
    if subscription is None:
        raise SubscriptionNotFoundError("monitoramento não encontrado")
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if values.get("enabled") is True and not subscription.enabled:
        await lock_user_subscription_quota(session, user_id=user_id)
        if await count_active_subscriptions(session, user_id=user_id) >= MAX_ACTIVE_SUBSCRIPTIONS_PER_USER:
            raise SubscriptionLimitError("limite de monitoramentos ativos atingido")
    for field, value in values.items():
        setattr(subscription, field, value)
    await save_subscription(session, subscription)
    logger.info(
        "investment_alert.subscription_updated",
        extra={
            "event": "investment_alert.subscription_updated",
            "user_id": user_id,
            "asset": subscription.asset,
            "subscription_id": subscription.id,
            "status": "ACTIVE" if subscription.enabled else "PAUSED",
        },
    )
    return subscription


async def remove_monitoring_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
) -> None:
    subscription = await get_owned_subscription(
        session, user_id=user_id, subscription_id=subscription_id
    )
    if subscription is None:
        raise SubscriptionNotFoundError("monitoramento não encontrado")
    asset = subscription.asset
    await delete_subscription(session, subscription)
    logger.info(
        "investment_alert.subscription_deleted",
        extra={
            "event": "investment_alert.subscription_deleted",
            "user_id": user_id,
            "asset": asset,
            "subscription_id": subscription_id,
            "status": "DELETED",
        },
    )


async def _generate_or_reuse_audited_decision(
    *,
    subscription: InvestmentAlertSubscription,
    evaluation_key: str,
    effective_at: datetime,
    session_factory: async_sessionmaker[AsyncSession],
) -> InvestmentDecisionAudit:
    decision_id, correlation_id = _deterministic_trace_ids(evaluation_key)
    async with session_factory() as audit_session:
        existing = await get_decision_by_id(audit_session, decision_id=decision_id)
        if existing is not None:
            if existing.user_id != subscription.user_id:
                raise ValueError("deterministic decision ownership collision")
            return existing

        request_parameters = {
            "budget": subscription.budget,
            "market": subscription.market,
            "limit": MONITORING_RECOMMENDATION_LIMIT,
            "include_warnings": subscription.include_warnings,
            "profile": subscription.investor_profile,
            "trend_filter": subscription.trend_filter,
            "explain": True,
            "source": AUTOMATION_SOURCE,
            "subscription_id": subscription.id,
            "monitored_asset": subscription.asset,
        }
        started_at = perf_counter()
        with decision_trace_context(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=subscription.user_id,
        ):
            logger.info(
                "investment_alert.evaluation_started",
                extra={
                    "event": "investment_alert.evaluation_started",
                    "subscription_id": subscription.id,
                    "asset": subscription.asset,
                    "status": "STARTED",
                },
            )
            try:
                payload = await build_explained_budget_recommendations(
                    audit_session,
                    budget=subscription.budget,
                    market=subscription.market,
                    limit=MONITORING_RECOMMENDATION_LIMIT,
                    include_warnings=subscription.include_warnings,
                    profile=subscription.investor_profile,
                    trend_filter=subscription.trend_filter,
                )
                focused, found = _focused_payload(payload, subscription.asset)
                latency_ms = round((perf_counter() - started_at) * 1000)
                record = build_decision_audit(
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    user_id=subscription.user_id,
                    request_parameters=request_parameters,
                    payload=focused,
                    latency_ms=latency_ms,
                    status=STATUS_SUCCESS if found else STATUS_EMPTY,
                    created_at=effective_at,
                )
                persisted = await persist_decision_audit(audit_session, record)
                logger.info(
                    "investment_alert.evaluation_decision_persisted",
                    extra={
                        "event": "investment_alert.evaluation_decision_persisted",
                        "subscription_id": subscription.id,
                        "asset": subscription.asset,
                        "status": persisted.status,
                        "latency_ms": latency_ms,
                    },
                )
                return persisted
            except Exception as exc:
                latency_ms = round((perf_counter() - started_at) * 1000)
                error_record = build_decision_audit(
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    user_id=subscription.user_id,
                    request_parameters=request_parameters,
                    payload={},
                    latency_ms=latency_ms,
                    status=STATUS_ERROR,
                    error_code="ALERT_EVALUATION_ERROR",
                    created_at=effective_at,
                )
                await persist_decision_audit_fail_open(audit_session, error_record)
                logger.exception(
                    "investment_alert.evaluation_failed",
                    extra={
                        "event": "investment_alert.evaluation_failed",
                        "subscription_id": subscription.id,
                        "asset": subscription.asset,
                        "status": "FAILED",
                        "error_code": "ALERT_EVALUATION_ERROR",
                        "exception_type": type(exc).__name__,
                        "latency_ms": latency_ms,
                    },
                )
                raise


async def evaluate_subscription(
    *,
    subscription_id: int,
    effective_at: datetime | None = None,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, Any]:
    now = effective_at or _now_utc()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    evaluation_key = build_evaluation_key(subscription_id, now)

    async with session_factory() as coordination_session:
        pair = await get_subscription_state_for_update(
            coordination_session, subscription_id=subscription_id
        )
        if pair is None:
            await coordination_session.rollback()
            return {"status": "SKIPPED_DISABLED", "subscription_id": subscription_id}
        subscription, state = pair
        if state.last_evaluation_key == evaluation_key:
            state.duplicates_prevented_count += 1
            await coordination_session.commit()
            return {
                "status": "SKIPPED_DUPLICATE",
                "subscription_id": subscription_id,
                "duplicates_prevented": 1,
                "alerts_created": 0,
            }

        decision = await _generate_or_reuse_audited_decision(
            subscription=subscription,
            evaluation_key=evaluation_key,
            effective_at=now,
            session_factory=session_factory,
        )
        previous = observation_from_state(state)
        current = observation_from_decision(decision)
        candidates = detect_relevant_events(
            subscription_id=subscription.id,
            asset=subscription.asset,
            previous=previous,
            current=current,
            alert_on_action_change=subscription.alert_on_action_change,
            alert_on_score_change=subscription.alert_on_score_change,
            alert_on_confidence_change=subscription.alert_on_confidence_change,
            alert_on_risk_change=subscription.alert_on_risk_change,
            alert_on_new_opportunity=subscription.alert_on_new_opportunity,
            minimum_score_delta=Decimal(subscription.minimum_score_delta),
            minimum_confidence_delta=Decimal(subscription.minimum_confidence_delta),
        )
        latest = await latest_alerts_by_type(
            coordination_session,
            subscription_id=subscription.id,
            alert_types=[candidate.alert_type for candidate in candidates],
        )
        created = 0
        cooldown_suppressed = 0
        duplicates = 0
        distribution: dict[str, int] = {}
        for candidate in candidates:
            last_alert = latest.get(candidate.alert_type)
            if not cooldown_allows(
                candidate=candidate,
                last_created_at=last_alert.created_at if last_alert else None,
                last_deduplication_key=last_alert.deduplication_key if last_alert else None,
                now=now,
                cooldown_minutes=subscription.cooldown_minutes,
            ):
                cooldown_suppressed += 1
                logger.info(
                    "investment_alert.suppressed_cooldown",
                    extra={
                        "event": "investment_alert.suppressed_cooldown",
                        "user_id": subscription.user_id,
                        "subscription_id": subscription.id,
                        "decision_id": decision.decision_id,
                        "asset": subscription.asset,
                        "alert_type": candidate.alert_type,
                        "severity": candidate.severity,
                        "status": "SUPPRESSED",
                    },
                )
                continue
            alert_id = canonical_uuid(str(uuid4()))
            inserted = await insert_alert_if_absent(
                coordination_session,
                {
                    "alert_id": alert_id,
                    "deduplication_key": candidate.deduplication_key,
                    "user_id": subscription.user_id,
                    "subscription_id": subscription.id,
                    "decision_id": decision.decision_id,
                    "asset": subscription.asset,
                    "alert_type": candidate.alert_type,
                    "severity": candidate.severity,
                    "delivery_channel": DELIVERY_CHANNEL_IN_APP,
                    "previous_state": sanitize_snapshot(candidate.previous_state),
                    "current_state": sanitize_snapshot(candidate.current_state),
                    "message": candidate.message,
                    "rule_version": ALERT_RULE_VERSION,
                    "created_at": now,
                },
            )
            if inserted:
                created += 1
                distribution[candidate.alert_type] = distribution.get(candidate.alert_type, 0) + 1
                logger.info(
                    "investment_alert.generated",
                    extra={
                        "event": "investment_alert.generated",
                        "user_id": subscription.user_id,
                        "subscription_id": subscription.id,
                        "decision_id": decision.decision_id,
                        "alert_id": alert_id,
                        "asset": subscription.asset,
                        "alert_type": candidate.alert_type,
                        "severity": candidate.severity,
                        "status": "CREATED",
                    },
                )
            else:
                duplicates += 1

        state.last_decision_id = current.decision_id
        state.last_action = current.action
        state.last_score = current.score
        state.last_confidence = current.confidence
        state.last_risk_level = current.risk_level
        state.last_trend = current.trend
        state.last_checked_at = now
        state.last_evaluation_key = evaluation_key
        state.evaluations_count += 1
        state.alerts_generated_count += created
        state.cooldown_suppressed_count += cooldown_suppressed
        state.duplicates_prevented_count += duplicates
        await coordination_session.commit()
        return {
            "status": "SUCCESS",
            "subscription_id": subscription.id,
            "decision_id": decision.decision_id,
            "alerts_created": created,
            "cooldown_suppressed": cooldown_suppressed,
            "duplicates_prevented": duplicates,
            "by_type": distribution,
        }


async def evaluate_active_subscriptions(
    *,
    effective_at: datetime | None = None,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, Any]:
    now = effective_at or _now_utc()
    async with session_factory() as listing_session:
        subscription_ids = await list_active_subscription_ids(
            listing_session, limit=MAX_SUBSCRIPTIONS_PER_CYCLE
        )

    summary: dict[str, Any] = {
        "status": "SUCCESS",
        "subscriptions_scanned": len(subscription_ids),
        "evaluated": 0,
        "alerts_generated": 0,
        "cooldown_suppressed": 0,
        "duplicates_prevented": 0,
        "errors": 0,
        "by_type": {},
        "as_of": now.isoformat(),
        "rule_version": ALERT_RULE_VERSION,
    }
    for subscription_id in subscription_ids:
        if summary["alerts_generated"] > MAX_ALERTS_PER_CYCLE - MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION:
            break
        try:
            result = await evaluate_subscription(
                subscription_id=subscription_id,
                effective_at=now,
                session_factory=session_factory,
            )
            if result.get("status") == "SUCCESS":
                summary["evaluated"] += 1
            summary["alerts_generated"] += int(result.get("alerts_created", 0))
            summary["cooldown_suppressed"] += int(result.get("cooldown_suppressed", 0))
            summary["duplicates_prevented"] += int(result.get("duplicates_prevented", 0))
            for alert_type, total in (result.get("by_type") or {}).items():
                summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + int(total)
        except Exception as exc:
            summary["errors"] += 1
            async with session_factory() as error_session:
                try:
                    await increment_state_error(error_session, subscription_id=subscription_id)
                except Exception:
                    await error_session.rollback()
            logger.exception(
                "investment_alert.subscription_evaluation_failed",
                extra={
                    "event": "investment_alert.subscription_evaluation_failed",
                    "subscription_id": subscription_id,
                    "status": "FAILED",
                    "error_code": "SUBSCRIPTION_EVALUATION_FAILED",
                    "exception_type": type(exc).__name__,
                },
            )
            continue
    return summary


async def alert_metrics(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    return await get_alert_metrics(session, user_id=user_id)

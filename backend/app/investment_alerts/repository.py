from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.investment_alerts.models import (
    InvestmentAlert,
    InvestmentAlertState,
    InvestmentAlertSubscription,
)
from backend.app.investment_decisions.models import InvestmentDecisionAudit


class DuplicateSubscriptionError(ValueError):
    pass


async def get_owned_source_decision(
    session: AsyncSession,
    *,
    user_id: int,
    asset: str,
    decision_id: str | None,
) -> InvestmentDecisionAudit | None:
    statement = select(InvestmentDecisionAudit).where(
        InvestmentDecisionAudit.user_id == user_id,
        InvestmentDecisionAudit.asset == asset,
        InvestmentDecisionAudit.status == "SUCCESS",
    )
    if decision_id:
        statement = statement.where(InvestmentDecisionAudit.decision_id == decision_id)
    else:
        statement = statement.order_by(
            InvestmentDecisionAudit.created_at.desc(), InvestmentDecisionAudit.id.desc()
        ).limit(1)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def count_active_subscriptions(session: AsyncSession, *, user_id: int) -> int:
    result = await session.execute(
        select(func.count(InvestmentAlertSubscription.id)).where(
            InvestmentAlertSubscription.user_id == user_id,
            InvestmentAlertSubscription.enabled.is_(True),
        )
    )
    return int(result.scalar_one())


async def lock_user_subscription_quota(session: AsyncSession, *, user_id: int) -> None:
    """Serialize create/enable quota checks on PostgreSQL without a new lock service."""

    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(select(func.pg_advisory_xact_lock(370_037, user_id)))


async def get_owned_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
) -> InvestmentAlertSubscription | None:
    result = await session.execute(
        select(InvestmentAlertSubscription).where(
            InvestmentAlertSubscription.id == subscription_id,
            InvestmentAlertSubscription.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_owned_subscription_by_asset(
    session: AsyncSession,
    *,
    user_id: int,
    asset: str,
) -> InvestmentAlertSubscription | None:
    result = await session.execute(
        select(InvestmentAlertSubscription).where(
            InvestmentAlertSubscription.user_id == user_id,
            InvestmentAlertSubscription.asset == asset,
        )
    )
    return result.scalar_one_or_none()


async def list_owned_subscriptions(
    session: AsyncSession,
    *,
    user_id: int,
) -> list[InvestmentAlertSubscription]:
    result = await session.execute(
        select(InvestmentAlertSubscription)
        .where(InvestmentAlertSubscription.user_id == user_id)
        .order_by(
            InvestmentAlertSubscription.enabled.desc(),
            InvestmentAlertSubscription.updated_at.desc(),
            InvestmentAlertSubscription.id.desc(),
        )
    )
    return list(result.scalars().all())


async def create_subscription_with_state(
    session: AsyncSession,
    *,
    subscription: InvestmentAlertSubscription,
    state: InvestmentAlertState,
) -> InvestmentAlertSubscription:
    session.add(subscription)
    try:
        await session.flush()
        state.subscription_id = subscription.id
        session.add(state)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateSubscriptionError("ativo já monitorado") from exc
    return subscription


async def save_subscription(session: AsyncSession, subscription: InvestmentAlertSubscription) -> None:
    await session.commit()
    await session.refresh(subscription)


async def delete_subscription(session: AsyncSession, subscription: InvestmentAlertSubscription) -> None:
    await session.delete(subscription)
    await session.commit()


async def list_active_subscription_ids(session: AsyncSession, *, limit: int) -> list[int]:
    result = await session.execute(
        select(InvestmentAlertSubscription.id)
        .where(InvestmentAlertSubscription.enabled.is_(True))
        .order_by(InvestmentAlertSubscription.updated_at.asc(), InvestmentAlertSubscription.id.asc())
        .limit(limit)
    )
    return [int(value) for value in result.scalars().all()]


async def get_subscription_state_for_update(
    session: AsyncSession,
    *,
    subscription_id: int,
) -> tuple[InvestmentAlertSubscription, InvestmentAlertState] | None:
    result = await session.execute(
        select(InvestmentAlertSubscription, InvestmentAlertState)
        .join(
            InvestmentAlertState,
            InvestmentAlertState.subscription_id == InvestmentAlertSubscription.id,
        )
        .where(
            InvestmentAlertSubscription.id == subscription_id,
            InvestmentAlertSubscription.enabled.is_(True),
        )
        .with_for_update(of=InvestmentAlertState)
    )
    row = result.one_or_none()
    return (row[0], row[1]) if row else None


async def get_decision_by_id(
    session: AsyncSession,
    *,
    decision_id: str,
) -> InvestmentDecisionAudit | None:
    result = await session.execute(
        select(InvestmentDecisionAudit).where(InvestmentDecisionAudit.decision_id == decision_id)
    )
    return result.scalar_one_or_none()


async def latest_alerts_by_type(
    session: AsyncSession,
    *,
    subscription_id: int,
    alert_types: Sequence[str],
) -> dict[str, InvestmentAlert]:
    if not alert_types:
        return {}
    result = await session.execute(
        select(InvestmentAlert)
        .where(
            InvestmentAlert.subscription_id == subscription_id,
            InvestmentAlert.alert_type.in_(alert_types),
        )
        .order_by(InvestmentAlert.created_at.desc(), InvestmentAlert.id.desc())
    )
    latest: dict[str, InvestmentAlert] = {}
    for alert in result.scalars().all():
        latest.setdefault(alert.alert_type, alert)
    return latest


async def insert_alert_if_absent(session: AsyncSession, payload: dict[str, Any]) -> bool:
    statement = (
        pg_insert(InvestmentAlert)
        .values(**payload)
        .on_conflict_do_nothing(index_elements=[InvestmentAlert.deduplication_key])
        .returning(InvestmentAlert.id)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none() is not None


def _alert_filters(
    *,
    user_id: int,
    asset: str | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    unread_only: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Any]:
    filters: list[Any] = [InvestmentAlert.user_id == user_id]
    if asset:
        filters.append(InvestmentAlert.asset == asset)
    if alert_type:
        filters.append(InvestmentAlert.alert_type == alert_type)
    if severity:
        filters.append(InvestmentAlert.severity == severity)
    if unread_only:
        filters.append(InvestmentAlert.read_at.is_(None))
    if date_from:
        filters.append(InvestmentAlert.created_at >= date_from)
    if date_to:
        filters.append(InvestmentAlert.created_at <= date_to)
    return filters


async def list_owned_alerts(
    session: AsyncSession,
    *,
    user_id: int,
    page: int,
    page_size: int,
    asset: str | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    unread_only: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    filters = _alert_filters(
        user_id=user_id,
        asset=asset,
        alert_type=alert_type,
        severity=severity,
        unread_only=unread_only,
        date_from=date_from,
        date_to=date_to,
    )
    total = int((await session.execute(select(func.count(InvestmentAlert.id)).where(*filters))).scalar_one())
    unread_count = int(
        (
            await session.execute(
                select(func.count(InvestmentAlert.id)).where(
                    InvestmentAlert.user_id == user_id,
                    InvestmentAlert.read_at.is_(None),
                )
            )
        ).scalar_one()
    )
    items = (
        await session.execute(
            select(InvestmentAlert)
            .where(*filters)
            .order_by(InvestmentAlert.created_at.desc(), InvestmentAlert.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": list(items),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "unread_count": unread_count,
    }


async def get_owned_alert(
    session: AsyncSession,
    *,
    user_id: int,
    alert_id: str,
) -> InvestmentAlert | None:
    result = await session.execute(
        select(InvestmentAlert).where(
            InvestmentAlert.alert_id == alert_id,
            InvestmentAlert.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_owned_alert_read(
    session: AsyncSession,
    *,
    user_id: int,
    alert_id: str,
    read_at: datetime,
) -> InvestmentAlert | None:
    alert = await get_owned_alert(session, user_id=user_id, alert_id=alert_id)
    if alert is None:
        return None
    if alert.read_at is None:
        alert.read_at = read_at
        await session.commit()
        await session.refresh(alert)
    return alert


async def increment_state_error(session: AsyncSession, *, subscription_id: int) -> None:
    result = await session.execute(
        select(InvestmentAlertState)
        .where(InvestmentAlertState.subscription_id == subscription_id)
        .with_for_update()
    )
    state = result.scalar_one_or_none()
    if state is not None:
        state.errors_count += 1
        await session.commit()


async def get_alert_metrics(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    subscription_summary = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(case((InvestmentAlertSubscription.enabled.is_(True), 1), else_=0)), 0
                ).label("active_subscriptions")
            ).where(InvestmentAlertSubscription.user_id == user_id)
        )
    ).mappings().one()
    state_summary = (
        await session.execute(
            select(
                func.coalesce(func.sum(InvestmentAlertState.evaluations_count), 0).label("evaluations"),
                func.coalesce(func.sum(InvestmentAlertState.alerts_generated_count), 0).label("generated"),
                func.coalesce(func.sum(InvestmentAlertState.cooldown_suppressed_count), 0).label("cooldown"),
                func.coalesce(func.sum(InvestmentAlertState.duplicates_prevented_count), 0).label("duplicates"),
                func.coalesce(func.sum(InvestmentAlertState.volume_suppressed_count), 0).label("volume"),
                func.coalesce(func.sum(InvestmentAlertState.errors_count), 0).label("errors"),
            ).where(InvestmentAlertState.user_id == user_id)
        )
    ).mappings().one()
    unread = int(
        (
            await session.execute(
                select(func.count(InvestmentAlert.id)).where(
                    InvestmentAlert.user_id == user_id,
                    InvestmentAlert.read_at.is_(None),
                )
            )
        ).scalar_one()
    )
    type_rows = (
        await session.execute(
            select(InvestmentAlert.alert_type, func.count(InvestmentAlert.id))
            .where(InvestmentAlert.user_id == user_id)
            .group_by(InvestmentAlert.alert_type)
            .order_by(InvestmentAlert.alert_type.asc())
        )
    ).all()
    return {
        "active_subscriptions": int(subscription_summary["active_subscriptions"] or 0),
        "evaluations_performed": int(state_summary["evaluations"] or 0),
        "alerts_generated": int(state_summary["generated"] or 0),
        "cooldown_suppressed": int(state_summary["cooldown"] or 0),
        "duplicates_prevented": int(state_summary["duplicates"] or 0),
        "volume_suppressed": int(state_summary["volume"] or 0),
        "errors": int(state_summary["errors"] or 0),
        "unread_alerts": unread,
        "by_type": {str(alert_type): int(total) for alert_type, total in type_rows},
    }

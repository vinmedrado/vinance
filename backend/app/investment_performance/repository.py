from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_performance.models import InvestmentDecisionPerformance
from backend.app.market.models.prices import AssetPrice


VALID_ACTIONS = ("BUY", "WAIT", "AVOID")
VALID_AUDIT_STATUS = "SUCCESS"


def valid_decision_statement(
    *,
    user_id: int | None = None,
    asset: str | None = None,
    action: str | None = None,
    risk_level: str | None = None,
    investor_profile: str | None = None,
    rule_version: str | None = None,
    recommendation_engine_version: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select[tuple[InvestmentDecisionAudit]]:
    filters: list[Any] = [
        InvestmentDecisionAudit.status == VALID_AUDIT_STATUS,
        InvestmentDecisionAudit.recommendation.in_(VALID_ACTIONS),
        InvestmentDecisionAudit.asset.is_not(None),
        InvestmentDecisionAudit.market.is_not(None),
    ]
    if user_id is not None:
        filters.append(InvestmentDecisionAudit.user_id == user_id)
    if asset:
        filters.append(InvestmentDecisionAudit.asset == asset.strip().upper())
    if action:
        filters.append(InvestmentDecisionAudit.recommendation == action.strip().upper())
    if risk_level:
        filters.append(InvestmentDecisionAudit.risk_level == risk_level.strip().upper())
    if investor_profile:
        filters.append(InvestmentDecisionAudit.investor_profile == investor_profile.strip().upper())
    if rule_version:
        filters.append(InvestmentDecisionAudit.rule_version == rule_version.strip())
    if recommendation_engine_version:
        filters.append(
            InvestmentDecisionAudit.recommendation_engine_version
            == recommendation_engine_version.strip()
        )
    if date_from:
        filters.append(InvestmentDecisionAudit.created_at >= date_from)
    if date_to:
        filters.append(InvestmentDecisionAudit.created_at <= date_to)
    return select(InvestmentDecisionAudit).where(*filters)


async def list_valid_decisions(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    asset: str | None = None,
    action: str | None = None,
    risk_level: str | None = None,
    investor_profile: str | None = None,
    rule_version: str | None = None,
    recommendation_engine_version: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    matured_before: datetime | None = None,
    limit: int | None = None,
) -> list[InvestmentDecisionAudit]:
    statement = valid_decision_statement(
        user_id=user_id,
        asset=asset,
        action=action,
        risk_level=risk_level,
        investor_profile=investor_profile,
        rule_version=rule_version,
        recommendation_engine_version=recommendation_engine_version,
        date_from=date_from,
        date_to=date_to,
    )
    if matured_before is not None:
        statement = statement.where(InvestmentDecisionAudit.created_at <= matured_before)
    statement = statement.order_by(
        InvestmentDecisionAudit.created_at.asc(),
        InvestmentDecisionAudit.id.asc(),
    )
    if limit is not None:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def list_existing_horizons(
    session: AsyncSession,
    decision_ids: Sequence[str],
) -> dict[str, set[str]]:
    if not decision_ids:
        return {}
    result = await session.execute(
        select(
            InvestmentDecisionPerformance.decision_id,
            InvestmentDecisionPerformance.horizon,
        ).where(InvestmentDecisionPerformance.decision_id.in_(decision_ids))
    )
    existing: dict[str, set[str]] = {}
    for decision_id, horizon in result.all():
        existing.setdefault(str(decision_id), set()).add(str(horizon))
    return existing


async def list_performances_for_decisions(
    session: AsyncSession,
    decision_ids: Sequence[str],
    *,
    horizon: str | None = None,
) -> list[InvestmentDecisionPerformance]:
    if not decision_ids:
        return []
    statement = select(InvestmentDecisionPerformance).where(
        InvestmentDecisionPerformance.decision_id.in_(decision_ids)
    )
    if horizon:
        statement = statement.where(InvestmentDecisionPerformance.horizon == horizon)
    statement = statement.order_by(
        InvestmentDecisionPerformance.evaluated_at.asc(),
        InvestmentDecisionPerformance.id.asc(),
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_owned_decision(
    session: AsyncSession,
    *,
    user_id: int,
    decision_id: str,
) -> InvestmentDecisionAudit | None:
    result = await session.execute(
        valid_decision_statement(user_id=user_id).where(
            InvestmentDecisionAudit.decision_id == decision_id
        )
    )
    return result.scalar_one_or_none()


async def list_prices(
    session: AsyncSession,
    *,
    ticker: str,
    market: str,
    date_from: date,
    date_to: date,
    available_at: datetime,
    source: str | None = None,
) -> list[AssetPrice]:
    filters: list[Any] = [
        AssetPrice.ticker == ticker.strip().upper(),
        AssetPrice.market == market.strip().lower(),
        AssetPrice.date >= date_from,
        AssetPrice.date <= date_to,
        AssetPrice.close > 0,
        AssetPrice.created_at <= available_at,
    ]
    if source:
        filters.append(AssetPrice.source == source)
    result = await session.execute(
        select(AssetPrice)
        .where(*filters)
        .order_by(AssetPrice.date.asc(), AssetPrice.source.asc(), AssetPrice.id.asc())
    )
    return list(result.scalars().all())


async def insert_performances_if_absent(
    session: AsyncSession,
    rows: Sequence[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    statement = (
        pg_insert(InvestmentDecisionPerformance)
        .values(list(rows))
        .on_conflict_do_nothing(
            index_elements=[
                InvestmentDecisionPerformance.decision_id,
                InvestmentDecisionPerformance.horizon,
            ]
        )
        .returning(InvestmentDecisionPerformance.id)
    )
    result = await session.execute(statement)
    created = len(result.scalars().all())
    await session.commit()
    return created

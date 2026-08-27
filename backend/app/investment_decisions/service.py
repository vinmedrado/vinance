from __future__ import annotations

import math
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from uuid import UUID, uuid4

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_decisions.versions import (
    GUARDRAIL_VERSION,
    RECOMMENDATION_ENGINE_VERSION,
    RULE_VERSION,
    SCORE_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    TREND_VERSION,
)

logger = get_logger(__name__)

ACTION_BUY = "BUY"
ACTION_WAIT = "WAIT"
ACTION_AVOID = "AVOID"
ACTION_NONE = "NO_RECOMMENDATION"

STATUS_SUCCESS = "SUCCESS"
STATUS_EMPTY = "EMPTY"
STATUS_ERROR = "ERROR"

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "password",
    "passwd",
    "access_token",
    "refresh_token",
    "bearer",
    "cookie",
    "secret",
    "api_key",
    "apikey",
)
_ASSET_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,32}$")


def canonical_uuid(value: str | None = None) -> str:
    """Preserve canonical UUIDs and replace missing or unsafe values."""

    if value:
        try:
            return str(UUID(value.strip()))
        except (AttributeError, TypeError, ValueError):
            pass
    return str(uuid4())


def parse_decision_id(value: str) -> str | None:
    try:
        return str(UUID(value.strip()))
    except (AttributeError, TypeError, ValueError):
        return None


def normalize_asset_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not _ASSET_PATTERN.fullmatch(normalized):
        raise ValueError("asset inválido")
    return normalized


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, UUID)):
        return value.isoformat() if not isinstance(value, UUID) else str(value)
    if isinstance(value, str) and value.lstrip().lower().startswith("bearer "):
        return "[REDACTED]"
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return _json_value({key: item for key, item in vars(value).items() if not key.startswith("_")})
    return str(value)


def sanitize_snapshot(value: Any) -> Any:
    """Build a detached JSON-safe snapshot while removing secret-bearing keys."""

    return _json_value(value)


def _record(value: Any) -> dict[str, Any]:
    sanitized = sanitize_snapshot(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return converted if converted.is_finite() else None


def _integer(value: Any) -> int | None:
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    return converted if converted >= 0 else None


def _upper(value: Any, default: str = "") -> str:
    return str(value or default).strip().upper()


def _coalesce(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def derive_presented_action(best: Mapping[str, Any] | None) -> str:
    """Mirror the existing Phase 33/34 visual translation without changing engine scores."""

    if not best:
        return ACTION_NONE
    decision_card = best.get("decision_card") if isinstance(best.get("decision_card"), Mapping) else {}
    status = _upper(best.get("status"))
    risk = _upper(best.get("risk_level"), "UNKNOWN")
    appreciation = _upper(_coalesce(best.get("appreciation_signal"), decision_card.get("appreciation_signal")), "UNKNOWN")
    trend = _upper(best.get("trend_label"))
    confidence_label = _upper(best.get("confidence_label"))
    recommendation_score = _decimal(_coalesce(best.get("recommendation_score"), decision_card.get("recommendation_score"))) or Decimal("0")
    confidence = _decimal(_coalesce(best.get("confidence_score"), decision_card.get("confidence_score"))) or Decimal("0")

    if risk == "HIGH" or status == "BLOCKED" or appreciation == "LOW":
        return ACTION_AVOID
    if trend in {"DOWNTREND", "SIDEWAYS"} or trend != "UPTREND":
        return ACTION_WAIT
    if appreciation == "UNKNOWN" or confidence_label == "LOW":
        return ACTION_WAIT
    if status == "APPROVED" and risk == "LOW" and recommendation_score >= 75 and confidence >= 80:
        return ACTION_BUY
    return ACTION_WAIT


def _best_and_alternatives(payload: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    snapshot = sanitize_snapshot(payload)
    if isinstance(snapshot, dict):
        best_value = snapshot.get("best_recommendation")
        best = best_value if isinstance(best_value, dict) else None
        alternatives = [item for item in snapshot.get("alternatives", []) if isinstance(item, dict)] if isinstance(snapshot.get("alternatives"), list) else []
        return best, alternatives, snapshot
    if isinstance(snapshot, list):
        candidates = [item for item in snapshot if isinstance(item, dict)]
        return (candidates[0] if candidates else None), candidates[1:], {"recommendations": candidates}
    return None, [], {}


def detect_fallback(payload: Any) -> bool:
    snapshot = sanitize_snapshot(payload)

    def visit(value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"fallback", "fallback_used"} and item is True:
                    return True
                if key in {"provider", "methodology", "trend_method", "source"} and "fallback" in str(item).lower():
                    return True
                if visit(item):
                    return True
        elif isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    return visit(snapshot)


def build_decision_audit(
    *,
    decision_id: str,
    correlation_id: str,
    user_id: int,
    request_parameters: Mapping[str, Any],
    payload: Any,
    latency_ms: int,
    status: str,
    error_code: str | None = None,
    created_at: datetime | None = None,
) -> InvestmentDecisionAudit:
    best, alternatives, response_snapshot = _best_and_alternatives(payload)
    best = best or {}
    decision_card = best.get("decision_card") if isinstance(best.get("decision_card"), dict) else {}
    relative_position = best.get("relative_position") if isinstance(best.get("relative_position"), dict) else {}
    score_breakdown = best.get("score_breakdown") if isinstance(best.get("score_breakdown"), dict) else {}
    request_snapshot = _record(request_parameters)
    budget = _decimal(request_snapshot.get("budget")) or _decimal(response_snapshot.get("budget")) or Decimal("0")
    invested = _decimal(_coalesce(best.get("invested_amount"), decision_card.get("invested_amount")))
    remaining = _decimal(_coalesce(best.get("remaining_budget"), decision_card.get("remaining_budget")))
    if remaining is None and invested is not None:
        remaining = budget - invested

    explanation_keys = (
        "recommendation_title",
        "decision_summary",
        "executive_summary",
        "why_recommended",
        "strengths",
        "attention_points",
        "comparison_with_alternatives",
        "appreciation_signal",
        "appreciation_text",
        "confidence_label",
        "explanation_quality",
        "disclaimer",
    )
    explanation = {key: best[key] for key in explanation_keys if key in best}
    score_snapshot = {
        "score_breakdown": score_breakdown,
        "recommendation_components": best.get("recommendation_components_json") or {},
        "score_total": best.get("score_total"),
        "profile_score": best.get("profile_score"),
        "recommendation_score": best.get("recommendation_score"),
        "momentum_score": best.get("momentum_score"),
    }
    input_snapshot = {
        "selected_candidate": best,
        "alternatives_considered": alternatives,
        "candidate_count": (1 if best else 0) + len(alternatives),
        "market": request_snapshot.get("market") or response_snapshot.get("market"),
        "profile": request_snapshot.get("profile") or response_snapshot.get("profile"),
    }

    return InvestmentDecisionAudit(
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        created_at=created_at,
        asset=str(best.get("ticker"))[:32] if best.get("ticker") else None,
        market=str(best.get("market") or response_snapshot.get("market") or request_snapshot.get("market") or "")[:24] or None,
        budget=budget,
        investor_profile=str(best.get("profile") or response_snapshot.get("profile") or request_snapshot.get("profile") or "")[:32] or None,
        recommendation=derive_presented_action(best),
        quantity=_integer(_coalesce(best.get("quantity_possible"), decision_card.get("quantity"))),
        price=_decimal(_coalesce(best.get("price"), decision_card.get("price"))),
        invested_amount=invested,
        remaining_amount=remaining,
        risk_level=_upper(best.get("risk_level"), "UNKNOWN")[:24] if best else None,
        confidence=_decimal(_coalesce(best.get("confidence_score"), decision_card.get("confidence_score"))),
        trend=_upper(best.get("trend_label"), "UNKNOWN")[:32] if best else None,
        ranking=_integer(relative_position.get("rank")),
        recommendation_score=_decimal(_coalesce(best.get("recommendation_score"), decision_card.get("recommendation_score"))),
        guardrail_status=_upper(best.get("status"), "UNKNOWN")[:24] if best else None,
        guardrail_reasons=_record(best.get("reasons_json")),
        explanation=_record(explanation),
        request_parameters=request_snapshot,
        input_snapshot=_record(input_snapshot),
        score_snapshot=_record(score_snapshot),
        response_snapshot=_record(response_snapshot),
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        recommendation_engine_version=RECOMMENDATION_ENGINE_VERSION,
        score_version=SCORE_VERSION,
        guardrail_version=GUARDRAIL_VERSION,
        trend_version=TREND_VERSION,
        latency_ms=max(int(latency_ms), 0),
        fallback_used=detect_fallback(payload),
        error_code=error_code,
        status=status,
    )


async def persist_decision_audit(session: AsyncSession, record: InvestmentDecisionAudit) -> InvestmentDecisionAudit:
    existing_result = await session.execute(
        select(InvestmentDecisionAudit).where(InvestmentDecisionAudit.decision_id == record.decision_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if (
            existing.user_id != record.user_id
            or existing.correlation_id != record.correlation_id
            or existing.request_parameters != record.request_parameters
        ):
            raise ValueError("decision_id collision detected")
        return existing

    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate_result = await session.execute(
            select(InvestmentDecisionAudit).where(InvestmentDecisionAudit.decision_id == record.decision_id)
        )
        duplicate = duplicate_result.scalar_one_or_none()
        if duplicate is not None:
            return duplicate
        raise
    return record


async def persist_decision_audit_fail_open(session: AsyncSession, record: InvestmentDecisionAudit) -> bool:
    try:
        await persist_decision_audit(session, record)
        return True
    except Exception as exc:
        try:
            await session.rollback()
        except Exception:
            pass
        logger.exception(
            "investment_decision.audit_persistence_failed",
            extra={
                "event": "investment_decision.audit_persistence_failed",
                "decision_id": record.decision_id,
                "correlation_id": record.correlation_id,
                "user_id": record.user_id,
                "asset": record.asset,
                "status": record.status,
                "latency_ms": record.latency_ms,
                "error_code": "AUDIT_PERSISTENCE_FAILED",
                "exception_type": type(exc).__name__,
            },
        )
        return False


def _history_filters(
    *,
    user_id: int,
    asset: str | None = None,
    recommendation: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    risk_level: str | None = None,
) -> list[Any]:
    filters: list[Any] = [InvestmentDecisionAudit.user_id == user_id]
    if asset:
        filters.append(InvestmentDecisionAudit.asset == normalize_asset_filter(asset))
    if recommendation:
        filters.append(InvestmentDecisionAudit.recommendation == recommendation)
    if date_from:
        filters.append(InvestmentDecisionAudit.created_at >= date_from)
    if date_to:
        filters.append(InvestmentDecisionAudit.created_at <= date_to)
    if risk_level:
        filters.append(InvestmentDecisionAudit.risk_level == risk_level)
    return filters


async def list_decision_history(
    session: AsyncSession,
    *,
    user_id: int,
    page: int,
    page_size: int,
    asset: str | None = None,
    recommendation: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    filters = _history_filters(
        user_id=user_id,
        asset=asset,
        recommendation=recommendation,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
    )
    total = int((await session.execute(select(func.count(InvestmentDecisionAudit.id)).where(*filters))).scalar_one())
    rows = (
        await session.execute(
            select(InvestmentDecisionAudit)
            .where(*filters)
            .order_by(InvestmentDecisionAudit.created_at.desc(), InvestmentDecisionAudit.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": list(rows),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


async def get_owned_decision(session: AsyncSession, *, user_id: int, decision_id: str) -> InvestmentDecisionAudit | None:
    result = await session.execute(
        select(InvestmentDecisionAudit).where(
            InvestmentDecisionAudit.decision_id == decision_id,
            InvestmentDecisionAudit.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_decision_metrics(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    own = InvestmentDecisionAudit.user_id == user_id
    summary = (
        await session.execute(
            select(
                func.count(InvestmentDecisionAudit.id).label("total_decisions"),
                func.coalesce(func.sum(case((InvestmentDecisionAudit.recommendation == ACTION_BUY, 1), else_=0)), 0).label("comprar"),
                func.coalesce(func.sum(case((InvestmentDecisionAudit.recommendation == ACTION_WAIT, 1), else_=0)), 0).label("aguardar"),
                func.coalesce(func.sum(case((InvestmentDecisionAudit.recommendation == ACTION_AVOID, 1), else_=0)), 0).label("evitar"),
                func.coalesce(func.sum(case((InvestmentDecisionAudit.status == STATUS_ERROR, 1), else_=0)), 0).label("errors"),
                func.coalesce(func.sum(case((InvestmentDecisionAudit.fallback_used.is_(True), 1), else_=0)), 0).label("fallbacks"),
                func.coalesce(func.avg(InvestmentDecisionAudit.latency_ms), 0).label("average_latency_ms"),
                func.coalesce(func.percentile_cont(0.95).within_group(InvestmentDecisionAudit.latency_ms), 0).label("p95_latency_ms"),
            ).where(own)
        )
    ).mappings().one()

    async def distribution(column: Any) -> dict[str, int]:
        rows = (
            await session.execute(
                select(column.label("key"), func.count(InvestmentDecisionAudit.id).label("total"))
                .where(own, column.is_not(None))
                .group_by(column)
                .order_by(func.count(InvestmentDecisionAudit.id).desc(), column.asc())
            )
        ).all()
        return {str(key): int(total) for key, total in rows}

    top_assets_rows = (
        await session.execute(
            select(InvestmentDecisionAudit.asset, func.count(InvestmentDecisionAudit.id).label("total"))
            .where(own, InvestmentDecisionAudit.asset.is_not(None))
            .group_by(InvestmentDecisionAudit.asset)
            .order_by(func.count(InvestmentDecisionAudit.id).desc(), InvestmentDecisionAudit.asset.asc())
            .limit(10)
        )
    ).all()
    return {
        "total_decisions": int(summary["total_decisions"] or 0),
        "comprar": int(summary["comprar"] or 0),
        "aguardar": int(summary["aguardar"] or 0),
        "evitar": int(summary["evitar"] or 0),
        "errors": int(summary["errors"] or 0),
        "fallbacks": int(summary["fallbacks"] or 0),
        "average_latency_ms": round(float(summary["average_latency_ms"] or 0), 2),
        "p95_latency_ms": round(float(summary["p95_latency_ms"] or 0), 2),
        "by_profile": await distribution(InvestmentDecisionAudit.investor_profile),
        "by_risk": await distribution(InvestmentDecisionAudit.risk_level),
        "top_assets": [{"asset": asset, "total": int(total)} for asset, total in top_assets_rows],
    }

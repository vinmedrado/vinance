from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median
from typing import Any, Callable, Iterable

from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_performance.config import (
    CALIBRATION_GAP_TOLERANCE_PCT,
    CALIBRATION_MIN_SAMPLE,
    CALIBRATION_STRONG_GAP_PCT,
    CONFIDENCE_BANDS,
    HORIZON_DAYS,
    SCORE_BANDS,
)
from backend.app.investment_performance.models import InvestmentDecisionPerformance


CORRECT_CLASSIFICATIONS = {"CORRECT", "STRONGLY_CORRECT"}
INCORRECT_CLASSIFICATIONS = {"INCORRECT", "STRONGLY_INCORRECT"}
NEUTRAL_CLASSIFICATION = "NEUTRAL"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        converted = Decimal(str(value))
    except Exception:
        return None
    return converted if converted.is_finite() else None


def _rounded(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 6)


def _evaluation_stats(items: Iterable[InvestmentDecisionPerformance]) -> dict[str, Any]:
    rows = list(items)
    returns = [value for item in rows if (value := _decimal(item.return_pct)) is not None]
    classifications = [str(item.result_classification).upper() for item in rows]
    directional = [
        item for item in classifications if item != NEUTRAL_CLASSIFICATION
    ]
    correct = sum(item in CORRECT_CLASSIFICATIONS for item in directional)
    return {
        "total": len(rows),
        "average_return_pct": _rounded(sum(returns, Decimal("0")) / len(returns)) if returns else None,
        "median_return_pct": _rounded(Decimal(str(median(returns)))) if returns else None,
        "positive_pct": _percentage(sum(value > 0 for value in returns), len(returns)),
        "negative_pct": _percentage(sum(value < 0 for value in returns), len(returns)),
        "directional_accuracy_pct": _percentage(correct, len(directional)),
        "directional_sample": len(directional),
        "neutral": sum(item == NEUTRAL_CLASSIFICATION for item in classifications),
    }


def _band_key(
    value: Any,
    bands: tuple[tuple[str, Decimal, Decimal | None], ...],
) -> str:
    converted = _decimal(value)
    if converted is None:
        return "UNKNOWN"
    for key, lower, upper in bands:
        if converted >= lower and (upper is None or converted < upper):
            return key
    return "OUT_OF_RANGE"


def _eligible_horizons(
    decision: InvestmentDecisionAudit,
    *,
    as_of: datetime,
    selected_horizon: str | None,
) -> list[str]:
    created_at = _as_utc(decision.created_at)
    return [
        horizon
        for horizon, days in HORIZON_DAYS.items()
        if (selected_horizon is None or horizon == selected_horizon)
        and created_at + timedelta(days=days) <= as_of
    ]


def _dimension_rows(
    decisions: list[InvestmentDecisionAudit],
    evaluations: list[InvestmentDecisionPerformance],
    *,
    key_fn: Callable[[InvestmentDecisionAudit], str],
    as_of: datetime,
    selected_horizon: str | None,
) -> list[dict[str, Any]]:
    decision_map = {decision.decision_id: decision for decision in decisions}
    eligible: dict[str, int] = defaultdict(int)
    grouped: dict[str, list[InvestmentDecisionPerformance]] = defaultdict(list)
    for decision in decisions:
        key = key_fn(decision) or "UNKNOWN"
        eligible[key] += len(
            _eligible_horizons(
                decision,
                as_of=as_of,
                selected_horizon=selected_horizon,
            )
        )
    for evaluation in evaluations:
        decision = decision_map.get(evaluation.decision_id)
        if decision is None:
            continue
        grouped[key_fn(decision) or "UNKNOWN"].append(evaluation)
    keys = sorted(set(eligible) | set(grouped))
    rows: list[dict[str, Any]] = []
    for key in keys:
        stats = _evaluation_stats(grouped.get(key, []))
        total_eligible = eligible.get(key, 0)
        rows.append(
            {
                "key": key,
                "total_eligible": total_eligible,
                "evaluated": stats["total"],
                "pending": max(total_eligible - stats["total"], 0),
                **stats,
            }
        )
    return rows


def _calibration(
    decisions: list[InvestmentDecisionAudit],
    evaluations: list[InvestmentDecisionPerformance],
    *,
    as_of: datetime,
    selected_horizon: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _dimension_rows(
        decisions,
        evaluations,
        key_fn=lambda decision: _band_key(decision.confidence, CONFIDENCE_BANDS),
        as_of=as_of,
        selected_horizon=selected_horizon,
    )
    decision_map = {decision.decision_id: decision for decision in decisions}
    confidences: dict[str, list[Decimal]] = defaultdict(list)
    for evaluation in evaluations:
        decision = decision_map.get(evaluation.decision_id)
        if decision is None:
            continue
        value = _decimal(decision.confidence)
        if value is not None:
            confidences[_band_key(value, CONFIDENCE_BANDS)].append(value)

    for row in rows:
        values = confidences.get(row["key"], [])
        mean_confidence = sum(values, Decimal("0")) / len(values) if values else None
        accuracy = _decimal(row["directional_accuracy_pct"])
        gap = mean_confidence - accuracy if mean_confidence is not None and accuracy is not None else None
        if row["directional_sample"] < CALIBRATION_MIN_SAMPLE or gap is None:
            diagnostic = "INSUFFICIENT_SAMPLE"
        elif gap >= CALIBRATION_STRONG_GAP_PCT:
            diagnostic = "OVERCONFIDENT"
        elif gap <= -CALIBRATION_STRONG_GAP_PCT:
            diagnostic = "UNDERCONFIDENT"
        elif abs(gap) <= CALIBRATION_GAP_TOLERANCE_PCT:
            diagnostic = "CONSISTENT"
        else:
            diagnostic = "REVIEW"
        row.update(
            {
                "mean_confidence": _rounded(mean_confidence),
                "calibration_gap_pct": _rounded(gap),
                "diagnostic": diagnostic,
            }
        )

    ordered = [
        next((row for row in rows if row["key"] == key), None)
        for key, _lower, _upper in CONFIDENCE_BANDS
    ]
    usable = [
        row
        for row in ordered
        if row
        and row["directional_accuracy_pct"] is not None
        and row["directional_sample"] >= CALIBRATION_MIN_SAMPLE
    ]
    monotonic = None
    separation = None
    if len(usable) >= 2:
        accuracies = [float(row["directional_accuracy_pct"]) for row in usable]
        monotonic = all(left <= right for left, right in zip(accuracies, accuracies[1:]))
        separation = round(accuracies[-1] - accuracies[0], 6)
    summary = {
        "monotonic_directional_accuracy": monotonic,
        "high_low_separation_pct": separation,
        "interpretation": (
            "INSUFFICIENT_SAMPLE"
            if len(usable) < 2
            else "USEFUL_SEPARATION"
            if monotonic and separation is not None and separation > 0
            else "LOW_OR_INVERTED_SEPARATION"
        ),
    }
    return rows, summary


def _timeline_rows(
    decisions: list[InvestmentDecisionAudit],
    evaluations: list[InvestmentDecisionPerformance],
    *,
    as_of: datetime,
    selected_horizon: str | None,
) -> list[dict[str, Any]]:
    decision_map = {decision.decision_id: decision for decision in decisions}
    eligible: dict[tuple[str, str], int] = defaultdict(int)
    grouped: dict[tuple[str, str], list[InvestmentDecisionPerformance]] = defaultdict(list)
    for decision in decisions:
        period = _as_utc(decision.created_at).strftime("%Y-%m")
        for horizon in _eligible_horizons(
            decision,
            as_of=as_of,
            selected_horizon=selected_horizon,
        ):
            eligible[(period, horizon)] += 1
    for evaluation in evaluations:
        decision = decision_map.get(evaluation.decision_id)
        if decision is None:
            continue
        period = _as_utc(decision.created_at).strftime("%Y-%m")
        grouped[(period, evaluation.horizon)].append(evaluation)
    rows: list[dict[str, Any]] = []
    horizon_order = {value: index for index, value in enumerate(HORIZON_DAYS)}
    for period, horizon in sorted(
        set(eligible) | set(grouped),
        key=lambda item: (item[0], horizon_order.get(item[1], len(horizon_order))),
    ):
        stats = _evaluation_stats(grouped.get((period, horizon), []))
        total_eligible = eligible.get((period, horizon), 0)
        rows.append(
            {
                "key": f"{period}:{horizon}",
                "period": period,
                "horizon": horizon,
                "total_eligible": total_eligible,
                "evaluated": stats["total"],
                "pending": max(total_eligible - stats["total"], 0),
                **stats,
            }
        )
    return rows


def _version_cohort_key(decision: InvestmentDecisionAudit) -> str:
    values = (
        decision.recommendation_engine_version,
        decision.rule_version,
        decision.score_version or "UNKNOWN",
        decision.guardrail_version or "UNKNOWN",
    )
    return " | ".join(values)


def build_performance_summary(
    decisions: Iterable[InvestmentDecisionAudit],
    evaluations: Iterable[InvestmentDecisionPerformance],
    *,
    as_of: datetime,
    horizon: str | None = None,
) -> dict[str, Any]:
    decision_rows = list(decisions)
    decision_map = {decision.decision_id: decision for decision in decision_rows}
    effective_as_of = _as_utc(as_of)
    evaluation_rows = [
        item
        for item in evaluations
        if item.decision_id in decision_map
        and item.horizon in HORIZON_DAYS
        and (horizon is None or item.horizon == horizon)
        and _as_utc(decision_map[item.decision_id].created_at)
        + timedelta(days=HORIZON_DAYS[item.horizon])
        <= effective_as_of
    ]
    eligible = sum(
        len(
            _eligible_horizons(
                decision,
                as_of=effective_as_of,
                selected_horizon=horizon,
            )
        )
        for decision in decision_rows
    )
    overall = _evaluation_stats(evaluation_rows)

    def dimension(key_fn: Callable[[InvestmentDecisionAudit], str]) -> list[dict[str, Any]]:
        return _dimension_rows(
            decision_rows,
            evaluation_rows,
            key_fn=key_fn,
            as_of=effective_as_of,
            selected_horizon=horizon,
        )

    by_horizon = dimension(lambda _decision: "ALL") if horizon else []
    if horizon:
        for row in by_horizon:
            row["key"] = horizon
    else:
        by_horizon = []
        for horizon_key in HORIZON_DAYS:
            horizon_evaluations = [item for item in evaluation_rows if item.horizon == horizon_key]
            horizon_eligible = sum(
                horizon_key
                in _eligible_horizons(
                    decision,
                    as_of=effective_as_of,
                    selected_horizon=horizon_key,
                )
                for decision in decision_rows
            )
            stats = _evaluation_stats(horizon_evaluations)
            by_horizon.append(
                {
                    "key": horizon_key,
                    "total_eligible": horizon_eligible,
                    "evaluated": stats["total"],
                    "pending": max(horizon_eligible - stats["total"], 0),
                    **stats,
                }
            )

    calibration, calibration_summary = _calibration(
        decision_rows,
        evaluation_rows,
        as_of=effective_as_of,
        selected_horizon=horizon,
    )
    version_cohorts = dimension(_version_cohort_key)
    cohort_versions = {
        _version_cohort_key(decision): {
            "recommendation_engine_version": decision.recommendation_engine_version,
            "rule_version": decision.rule_version,
            "score_version": decision.score_version or "UNKNOWN",
            "guardrail_version": decision.guardrail_version or "UNKNOWN",
        }
        for decision in decision_rows
    }
    for row in version_cohorts:
        row.update(cohort_versions.get(row["key"], {}))
    return {
        "as_of": effective_as_of,
        "selected_horizon": horizon,
        "total_decisions": len(decision_rows),
        "eligible_decisions": eligible,
        "evaluated": overall["total"],
        "pending": max(eligible - overall["total"], 0),
        "average_return_pct": overall["average_return_pct"],
        "median_return_pct": overall["median_return_pct"],
        "positive_pct": overall["positive_pct"],
        "negative_pct": overall["negative_pct"],
        "directional_accuracy_pct": overall["directional_accuracy_pct"],
        "directional_sample": overall["directional_sample"],
        "by_horizon": by_horizon,
        "by_action": dimension(lambda decision: decision.recommendation or "UNKNOWN"),
        "by_asset": dimension(lambda decision: decision.asset or "UNKNOWN"),
        "by_risk": dimension(lambda decision: decision.risk_level or "UNKNOWN"),
        "by_trend": dimension(lambda decision: decision.trend or "UNKNOWN"),
        "by_confidence": dimension(
            lambda decision: _band_key(decision.confidence, CONFIDENCE_BANDS)
        ),
        "by_score_band": dimension(
            lambda decision: _band_key(decision.recommendation_score, SCORE_BANDS)
        ),
        "by_profile": dimension(lambda decision: decision.investor_profile or "UNKNOWN"),
        "by_rule_version": dimension(lambda decision: decision.rule_version),
        "by_recommendation_engine_version": dimension(
            lambda decision: decision.recommendation_engine_version
        ),
        "by_score_version": dimension(lambda decision: decision.score_version or "UNKNOWN"),
        "by_guardrail_version": dimension(
            lambda decision: decision.guardrail_version or "UNKNOWN"
        ),
        "by_version_cohort": version_cohorts,
        "mixed_versions": len(version_cohorts) > 1,
        "calibration": calibration,
        "calibration_summary": calibration_summary,
        "timeline": _timeline_rows(
            decision_rows,
            evaluation_rows,
            as_of=effective_as_of,
            selected_horizon=horizon,
        ),
    }

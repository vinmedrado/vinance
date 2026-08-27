from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.investment_alerts.rules import (
    ALERT_RULE_VERSION,
    ALERT_TYPE_ACTION_CHANGE,
    ALERT_TYPE_CONFIDENCE_CHANGE,
    ALERT_TYPE_NEW_OPPORTUNITY,
    ALERT_TYPE_RISK_CHANGE,
    ALERT_TYPE_SCORE_CHANGE,
    EVENT_PRIORITY,
    HIGH_SEVERITY_BYPASSES_COOLDOWN,
    MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION,
    RISK_ORDER,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_MEDIUM,
    SEVERITY_ORDER,
    VALID_ACTIONS,
    VALID_RISK_LEVELS,
)


ACTION_LABELS = {
    "BUY": "Comprar",
    "WAIT": "Aguardar",
    "AVOID": "Evitar",
    "NO_RECOMMENDATION": "Sem recomendação",
}
RISK_LABELS = {"LOW": "Baixo", "MEDIUM": "Médio", "HIGH": "Alto", "UNKNOWN": "Indefinido"}


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _normalized(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _json_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def _score_text(value: Decimal | None) -> str:
    if value is None:
        return "indisponível"
    return f"{value.quantize(Decimal('0.1'))}".replace(".", ",")


@dataclass(frozen=True)
class Observation:
    decision_id: str | None
    action: str | None
    score: Decimal | None
    confidence: Decimal | None
    risk_level: str | None
    trend: str | None
    observed_at: datetime | None = None

    @classmethod
    def from_values(
        cls,
        *,
        decision_id: str | None,
        action: Any,
        score: Any,
        confidence: Any,
        risk_level: Any,
        trend: Any,
        observed_at: datetime | None = None,
    ) -> "Observation":
        return cls(
            decision_id=decision_id,
            action=_normalized(action),
            score=_decimal(score),
            confidence=_decimal(confidence),
            risk_level=_normalized(risk_level),
            trend=_normalized(trend),
            observed_at=observed_at,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action,
            "score": _json_decimal(self.score),
            "confidence": _json_decimal(self.confidence),
            "risk_level": self.risk_level,
            "trend": self.trend,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
        }


@dataclass(frozen=True)
class AlertCandidate:
    alert_type: str
    severity: str
    message: str
    previous_state: dict[str, Any]
    current_state: dict[str, Any]
    deduplication_key: str


def build_evaluation_key(subscription_id: int, effective_at: datetime, rule_version: str = ALERT_RULE_VERSION) -> str:
    """Return one stable key per subscription and configured daily source window."""

    aware = effective_at if effective_at.tzinfo else effective_at.replace(tzinfo=timezone.utc)
    raw = f"{rule_version}|subscription:{subscription_id}|date:{aware.astimezone(timezone.utc).date().isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_occurrence_key(
    *,
    subscription_id: int,
    alert_type: str,
    previous: Observation,
    current: Observation,
    material: dict[str, Any],
) -> str:
    payload = {
        "rule_version": ALERT_RULE_VERSION,
        "subscription_id": subscription_id,
        "alert_type": alert_type,
        "previous_decision_id": previous.decision_id,
        "previous": material.get("previous"),
        "current": material.get("current"),
        "direction": material.get("direction"),
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate(
    *,
    subscription_id: int,
    asset: str,
    alert_type: str,
    severity: str,
    message: str,
    previous: Observation,
    current: Observation,
    material: dict[str, Any],
) -> AlertCandidate:
    return AlertCandidate(
        alert_type=alert_type,
        severity=severity,
        message=message,
        previous_state=previous.snapshot(),
        current_state=current.snapshot(),
        deduplication_key=build_occurrence_key(
            subscription_id=subscription_id,
            alert_type=alert_type,
            previous=previous,
            current=current,
            material=material,
        ),
    )


def action_change_severity(previous: str, current: str) -> str:
    if (previous, current) in {("BUY", "AVOID"), ("WAIT", "BUY"), ("AVOID", "BUY")}:
        return SEVERITY_HIGH
    if (previous, current) in {("BUY", "WAIT"), ("WAIT", "AVOID")}:
        return SEVERITY_MEDIUM
    return SEVERITY_INFO


def risk_change_severity(previous: str, current: str) -> str:
    if current == "HIGH" and previous != "HIGH":
        return SEVERITY_HIGH
    if RISK_ORDER.get(current, 0) > RISK_ORDER.get(previous, 0):
        return SEVERITY_MEDIUM
    return SEVERITY_INFO


def detect_relevant_events(
    *,
    subscription_id: int,
    asset: str,
    previous: Observation,
    current: Observation,
    alert_on_action_change: bool,
    alert_on_score_change: bool,
    alert_on_confidence_change: bool,
    alert_on_risk_change: bool,
    alert_on_new_opportunity: bool,
    minimum_score_delta: Decimal,
    minimum_confidence_delta: Decimal,
) -> list[AlertCandidate]:
    events: list[AlertCandidate] = []
    previous_action = previous.action
    current_action = current.action
    new_opportunity = current_action == "BUY" and previous_action != "BUY"

    if new_opportunity and alert_on_new_opportunity:
        old_label = ACTION_LABELS.get(previous_action or "NO_RECOMMENDATION", "Sem recomendação")
        events.append(
            _candidate(
                subscription_id=subscription_id,
                asset=asset,
                alert_type=ALERT_TYPE_NEW_OPPORTUNITY,
                severity=SEVERITY_HIGH,
                message=(
                    f"Uma nova oportunidade para {asset} foi identificada pelos critérios atuais. "
                    f"A recomendação mudou de {old_label} para Comprar."
                ),
                previous=previous,
                current=current,
                material={"previous": previous_action, "current": current_action},
            )
        )
    elif (
        alert_on_action_change
        and previous_action in VALID_ACTIONS
        and current_action in VALID_ACTIONS
        and previous_action != current_action
    ):
        events.append(
            _candidate(
                subscription_id=subscription_id,
                asset=asset,
                alert_type=ALERT_TYPE_ACTION_CHANGE,
                severity=action_change_severity(previous_action, current_action),
                message=(
                    f"A recomendação de {asset} mudou de {ACTION_LABELS[previous_action]} "
                    f"para {ACTION_LABELS[current_action]}."
                ),
                previous=previous,
                current=current,
                material={"previous": previous_action, "current": current_action},
            )
        )

    if alert_on_score_change and previous.score is not None and current.score is not None:
        delta = current.score - previous.score
        if abs(delta) >= Decimal(minimum_score_delta):
            direction = "UP" if delta > 0 else "DOWN"
            events.append(
                _candidate(
                    subscription_id=subscription_id,
                    asset=asset,
                    alert_type=ALERT_TYPE_SCORE_CHANGE,
                    severity=SEVERITY_MEDIUM,
                    message=(
                        f"O score de {asset} apresentou mudança relevante: "
                        f"de {_score_text(previous.score)} para {_score_text(current.score)}."
                    ),
                    previous=previous,
                    current=current,
                    material={
                        "previous": _json_decimal(previous.score),
                        "current": _json_decimal(current.score),
                        "direction": direction,
                    },
                )
            )

    if alert_on_confidence_change and previous.confidence is not None and current.confidence is not None:
        delta = current.confidence - previous.confidence
        if abs(delta) >= Decimal(minimum_confidence_delta):
            direction = "UP" if delta > 0 else "DOWN"
            events.append(
                _candidate(
                    subscription_id=subscription_id,
                    asset=asset,
                    alert_type=ALERT_TYPE_CONFIDENCE_CHANGE,
                    severity=SEVERITY_MEDIUM,
                    message=(
                        f"A confiança quantitativa de {asset} mudou de "
                        f"{_score_text(previous.confidence)} para {_score_text(current.confidence)}."
                    ),
                    previous=previous,
                    current=current,
                    material={
                        "previous": _json_decimal(previous.confidence),
                        "current": _json_decimal(current.confidence),
                        "direction": direction,
                    },
                )
            )

    if (
        alert_on_risk_change
        and previous.risk_level in VALID_RISK_LEVELS
        and current.risk_level in VALID_RISK_LEVELS
        and previous.risk_level != current.risk_level
    ):
        events.append(
            _candidate(
                subscription_id=subscription_id,
                asset=asset,
                alert_type=ALERT_TYPE_RISK_CHANGE,
                severity=risk_change_severity(previous.risk_level, current.risk_level),
                message=(
                    f"O nível de risco de {asset} mudou de {RISK_LABELS[previous.risk_level]} "
                    f"para {RISK_LABELS[current.risk_level]}."
                ),
                previous=previous,
                current=current,
                material={"previous": previous.risk_level, "current": current.risk_level},
            )
        )

    return sorted(
        events,
        key=lambda event: (-SEVERITY_ORDER[event.severity], -EVENT_PRIORITY[event.alert_type]),
    )[:MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION]


def cooldown_allows(
    *,
    candidate: AlertCandidate,
    last_created_at: datetime | None,
    last_deduplication_key: str | None,
    now: datetime,
    cooldown_minutes: int,
) -> bool:
    if last_created_at is None:
        return True
    aware_now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    aware_last = last_created_at if last_created_at.tzinfo else last_created_at.replace(tzinfo=timezone.utc)
    if aware_now - aware_last >= timedelta(minutes=max(cooldown_minutes, 0)):
        return True
    return bool(
        HIGH_SEVERITY_BYPASSES_COOLDOWN
        and candidate.severity == SEVERITY_HIGH
        and candidate.deduplication_key != last_deduplication_key
    )

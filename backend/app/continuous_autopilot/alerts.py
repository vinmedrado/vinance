from __future__ import annotations

import hashlib
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.continuous_autopilot.privacy import (
    owner_id,
    visible_changes,
    visible_materiality,
)
from backend.app.continuous_autopilot.rules import (
    ALERT_BY_MATERIALITY,
    RULES_VERSION,
)
from backend.app.financial_state.models import HouseholdMember
from backend.app.investment_alerts.repository import insert_alert_if_absent
from backend.app.investment_alerts.rules import DELIVERY_CHANNEL_IN_APP


_SEVERITY = {
    "INFORMATIONAL": "INFO",
    "ACTION_RECOMMENDED": "MEDIUM",
    "IMPORTANT": "HIGH",
    "CRITICAL": "CRITICAL",
}


def _recipient_scope(
    changes: list[Mapping[str, Any]], *, recipient: int
) -> tuple[str, int | None]:
    if changes and all(
        item.get("ownership_scope") == "PERSONAL"
        and owner_id(item.get("owner_user_id")) == recipient
        for item in changes
    ):
        return "PERSONAL", recipient
    return "HOUSEHOLD", None


def _safe_summary(changes: list[Mapping[str, Any]]) -> str:
    for item in changes:
        reason = item.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()[:500]
    return "Seu plano financeiro mudou."


async def deliver_continuous_alert(
    session: AsyncSession,
    *,
    continuous_decision_id: int,
    household_id: int,
    payload: Mapping[str, Any],
    alert_episode: int,
) -> int:
    """Deliver an A6 decision through the existing IN_APP inbox, idempotently."""

    alert = payload.get("alert")
    alert_decision = str(payload.get("alert_decision") or "NO_ALERT")
    if alert_decision in {"NO_ALERT", "INFORMATIONAL"} or not isinstance(
        alert, Mapping
    ):
        return 0

    if alert_episode < 1:
        raise ValueError("alert_episode must be positive")
    result = await session.execute(
        select(HouseholdMember.user_id)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
        )
        .order_by(HouseholdMember.user_id.asc())
    )
    recipients = [int(value) for value in result.scalars().all()]

    created = 0
    base_key = str(alert.get("dedupe_key") or payload.get("decision_fingerprint"))
    for recipient in recipients:
        recipient_changes = visible_changes(payload, recipient=recipient)
        if not recipient_changes:
            continue
        local_materiality = visible_materiality(recipient_changes)
        local_alert_decision = ALERT_BY_MATERIALITY[local_materiality]
        if local_alert_decision in {"NO_ALERT", "INFORMATIONAL"}:
            continue
        ownership_scope, owner_user_id = _recipient_scope(
            recipient_changes, recipient=recipient
        )
        safe_summary = _safe_summary(recipient_changes)
        hidden_changes = len(recipient_changes) != len(
            [
                item
                for item in payload.get("detected_changes", [])
                if isinstance(item, Mapping)
            ]
        )
        visible_ids = ",".join(
            sorted(
                str(item.get("change_id"))
                for item in recipient_changes
                if item.get("change_id")
            )
        )
        dedupe_key = hashlib.sha256(
            (
                f"continuous-autopilot:{base_key}:episode:{alert_episode}:"
                f"recipient:{recipient}:decision:{local_alert_decision}:"
                f"changes:{visible_ids}"
            ).encode("utf-8")
        ).hexdigest()
        alert_id = str(
            uuid5(NAMESPACE_URL, f"vinanceos:continuous-autopilot-alert:{dedupe_key}")
        )
        inserted = await insert_alert_if_absent(
            session,
            {
                "alert_id": alert_id,
                "deduplication_key": dedupe_key,
                "user_id": recipient,
                "subscription_id": None,
                "decision_id": None,
                "asset": None,
                "source_domain": "CONTINUOUS_AUTOPILOT",
                "source_reference": f"continuous-autopilot:{continuous_decision_id}",
                "household_id": household_id,
                "continuous_decision_id": continuous_decision_id,
                "ownership_scope": ownership_scope,
                "owner_user_id": owner_user_id,
                "alert_type": "CONTINUOUS_AUTOPILOT_CHANGE",
                "severity": _SEVERITY[local_alert_decision],
                "delivery_channel": DELIVERY_CHANNEL_IN_APP,
                "previous_state": {
                    "status": (
                        (payload.get("plan_diff") or {})
                        .get("status_change", {})
                        .get("previous")
                        if any(
                            item.get("change_type") == "PLAN_STATUS_CHANGED"
                            for item in recipient_changes
                        )
                        and isinstance(
                            (payload.get("plan_diff") or {}).get("status_change"),
                            Mapping,
                        )
                        else None
                    ),
                    "summary": safe_summary,
                    "fingerprint": (
                        None
                        if hidden_changes
                        else payload.get("previous_fingerprint")
                    ),
                },
                "current_state": {
                    "status": "CHANGED",
                    "summary": safe_summary,
                    "materiality": local_materiality,
                    "fingerprint": (
                        None if hidden_changes else payload.get("current_fingerprint")
                    ),
                },
                "message": safe_summary,
                "rule_version": RULES_VERSION,
                "created_at": payload.get("generated_at"),
            },
        )
        created += int(inserted)
    return created

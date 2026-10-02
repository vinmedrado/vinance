from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from backend.app.continuous_autopilot.rules import (
    ALERT_BY_MATERIALITY,
    CHANGE_CATEGORIES,
    MATERIALITY_ORDER,
    RULES_VERSION,
    reevaluation_scope,
)


def owner_id(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def scoped_visible(value: Mapping[str, Any], *, recipient: int) -> bool:
    scope = str(value.get("ownership_scope") or "").upper()
    if scope == "PERSONAL":
        return owner_id(value.get("owner_user_id")) == recipient
    if scope in {"", "HOUSEHOLD"}:
        return True
    return False


def change_visible(change: Mapping[str, Any], *, recipient: int) -> bool:
    if not scoped_visible(change, recipient=recipient):
        return False
    # Ownership may change between the two frozen values. Check both sides so
    # PERSONAL B -> HOUSEHOLD cannot reveal B's old value to member A.
    for field in ("previous_value", "current_value"):
        value = change.get(field)
        if isinstance(value, Mapping) and not scoped_visible(
            value, recipient=recipient
        ):
            return False
    return True


def visible_changes(
    payload: Mapping[str, Any], *, recipient: int
) -> list[dict[str, Any]]:
    return [
        deepcopy(dict(item))
        for item in payload.get("detected_changes", [])
        if isinstance(item, Mapping) and change_visible(item, recipient=recipient)
    ]


def visible_materiality(changes: Sequence[Mapping[str, Any]]) -> str:
    values = [
        str(item.get("materiality") or "NONE").upper()
        for item in changes
        if str(item.get("materiality") or "NONE").upper() in MATERIALITY_ORDER
    ]
    return max(values or ["NONE"], key=lambda item: MATERIALITY_ORDER[item])


def _visible_action(value: Any, *, recipient: int) -> bool:
    return isinstance(value, Mapping) and scoped_visible(value, recipient=recipient)


def _local_alert(
    payload: Mapping[str, Any],
    *,
    recipient: int,
    changes: Sequence[Mapping[str, Any]],
    materiality: str,
) -> dict[str, Any] | None:
    decision = ALERT_BY_MATERIALITY[materiality]
    if decision == "NO_ALERT" or not changes:
        return None
    primary = max(
        changes,
        key=lambda item: MATERIALITY_ORDER[
            str(item.get("materiality") or "NONE").upper()
        ],
    )
    reasons = [
        str(item.get("reason")).strip()
        for item in changes
        if isinstance(item.get("reason"), str) and str(item.get("reason")).strip()
    ]
    identity = {
        "decision_fingerprint": payload.get("decision_fingerprint"),
        "recipient": recipient,
        "alert_decision": decision,
        "visible_change_ids": sorted(
            str(item.get("change_id")) for item in changes if item.get("change_id")
        ),
    }
    dedupe_key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "severity": decision,
        "category": primary.get("category"),
        "title": (
            "Acao financeira critica"
            if decision == "CRITICAL"
            else "Seu plano financeiro mudou"
        ),
        "summary": reasons[0] if reasons else "Seu plano financeiro mudou.",
        "what_changed": reasons[:5],
        "why_it_matters": "A mudanca altera a parte do plano visivel para voce.",
        "recommended_action": (
            "Revise o novo plano antes de tomar outra decisao financeira."
            if decision in {"IMPORTANT", "CRITICAL"}
            else "Consulte as mudancas e siga a nova ordem de acoes."
        ),
        "previous_reference": {
            "action_plan_id": payload.get("previous_action_plan_id"),
            "fingerprint": payload.get("previous_fingerprint"),
        },
        "current_reference": {
            "action_plan_id": payload.get("current_action_plan_id"),
            "fingerprint": payload.get("current_fingerprint"),
        },
        "dedupe_key": dedupe_key,
    }


def project_decision_for_user(
    payload: Mapping[str, Any],
    *,
    user_id: int,
    shared_household: bool,
) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    if not shared_household:
        return result

    canonical_changes = [
        item
        for item in payload.get("detected_changes", [])
        if isinstance(item, Mapping)
    ]
    changes = visible_changes(payload, recipient=user_id)
    result["detected_changes"] = changes

    original_diff = payload.get("plan_diff")
    diff = deepcopy(dict(original_diff)) if isinstance(original_diff, Mapping) else {}
    original_added = list(diff.get("added_actions") or [])
    original_removed = list(diff.get("removed_actions") or [])
    original_changed = list(diff.get("changed_actions") or [])
    diff["added_actions"] = [
        deepcopy(item)
        for item in original_added
        if _visible_action(item, recipient=user_id)
    ]
    diff["removed_actions"] = [
        deepcopy(item)
        for item in original_removed
        if _visible_action(item, recipient=user_id)
    ]
    diff["changed_actions"] = [
        deepcopy(item)
        for item in original_changed
        if isinstance(item, Mapping)
        and _visible_action(item.get("before"), recipient=user_id)
        and _visible_action(item.get("after"), recipient=user_id)
    ]
    visible_action_ids = {
        str(item.get("entity_id"))
        for item in changes
        if item.get("entity_type") == "ACTION_PLAN_ACTION"
        and item.get("entity_id") is not None
    }
    diff["priority_changes"] = [
        deepcopy(item)
        for item in diff.get("priority_changes") or []
        if isinstance(item, Mapping)
        and str(item.get("action_id")) in visible_action_ids
    ]
    # Unchanged action IDs carry no ownership in the A6 payload.
    diff["unchanged_actions"] = []

    hidden = (
        len(changes) != len(canonical_changes)
        or len(diff["added_actions"]) != len(original_added)
        or len(diff["removed_actions"]) != len(original_removed)
        or len(diff["changed_actions"]) != len(original_changed)
    )
    categories = sorted(
        {
            str(item.get("category") or "").upper()
            for item in changes
            if str(item.get("category") or "").upper() in CHANGE_CATEGORIES
        }
    )
    materiality = visible_materiality(changes)
    alert_decision = ALERT_BY_MATERIALITY[materiality]
    local_scope = reevaluation_scope(categories)

    if hidden:
        local_status = "CHANGED" if changes else "UNCHANGED"
        result.update(
            {
                "status": local_status,
                "materiality": materiality,
                "alert_decision": alert_decision,
                "change_categories": categories,
                "reevaluation_scope": local_scope,
            }
        )
        diff.update(
            {
                "financial_delta": None,
                "investment_delta": None,
                "hold_cash_delta": None,
                "materiality": materiality,
                "summary": (
                    f"{len(changes)} mudanca(s) visivel(is) foram identificadas."
                    if changes
                    else "Nenhuma mudanca relevante visivel para voce foi identificada."
                ),
                "status_change": (
                    diff.get("status_change")
                    if any(
                        item.get("change_type") == "PLAN_STATUS_CHANGED"
                        for item in changes
                    )
                    else None
                ),
            }
        )
        result["alert"] = _local_alert(
            payload,
            recipient=user_id,
            changes=changes,
            materiality=materiality,
        )
        result["evidence"] = [
            {
                "code": "ACTION_PLAN_COMPARISON",
                "previous_action_plan_id": payload.get("previous_action_plan_id"),
                "current_action_plan_id": payload.get("current_action_plan_id"),
                "previous_fingerprint": payload.get("previous_fingerprint"),
                "current_fingerprint": payload.get("current_fingerprint"),
                "change_count": len(changes),
            }
        ]
        result["rule_traces"] = [
            {
                "rule_id": "CAP-DEPENDENCY-GATE",
                "rule_version": RULES_VERSION,
                "outcome": local_scope,
                "observed_categories": categories,
            },
            {
                "rule_id": "CAP-MATERIALITY",
                "rule_version": RULES_VERSION,
                "outcome": materiality,
                "change_count": len(changes),
            },
            {
                "rule_id": "CAP-ALERT-DECISION",
                "rule_version": RULES_VERSION,
                "outcome": alert_decision,
            },
        ]
        if result.get("operational_status") in {
            "UP_TO_DATE",
            "CHANGED",
            "UNCHANGED",
            "BLOCKED",
        }:
            result["operational_status"] = local_status

    result["plan_diff"] = diff
    # Dirty categories and unscoped A5 messages do not encode owner identity;
    # fail closed for shared-household member projections.
    result["pending_categories"] = []
    result["blockers"] = []
    result["warnings"] = []
    result["missing_information"] = []
    return result


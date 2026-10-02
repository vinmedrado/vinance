from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from backend.app.continuous_autopilot.rules import (
    ACTION_ADD_REMOVE_MATERIALITY,
    ACTION_CATEGORY_PREFERENCES,
    ACTION_CRITICAL_SEVERITIES,
    ACTION_IGNORED_FIELDS,
    ACTION_MATERIAL_FIELDS,
    ACTION_OTHER_CHANGE_MATERIALITY,
    ACTION_REMOVED_BUY_MATERIALITY,
    ACTION_TRANSITIONS,
    ALERT_BY_MATERIALITY,
    ALLOCATION_STATUS_ADVERSE,
    ALLOCATION_STATUS_MATERIALITY,
    CHANGE_CATEGORIES,
    CHANGE_SEVERITY_BY_MATERIALITY,
    CRITICAL_TRANSITIONS,
    DATA_QUALITY_ADVERSE,
    DATA_QUALITY_MATERIALITY,
    ENGINE_VERSION,
    FINGERPRINT_ONLY_MATERIALITY,
    HIGH_TRANSITIONS,
    INITIAL_STATUS_BY_ACTION_PLAN_STATUS,
    MATERIALITY_ORDER,
    MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD,
    MONETARY_MATERIALITY,
    ORCHESTRATION_STATUS_ADVERSE,
    ORCHESTRATION_STATUS_MATERIALITY,
    PLAN_STATUS_MATERIALITY,
    POLICY_STATE_CHANGE_MATERIALITY,
    READINESS_DEFAULT_MATERIALITY,
    RULESET,
    RULESET_FINGERPRINT,
    RULES_VERSION,
    reevaluation_scope as rules_reevaluation_scope,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _money(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money_delta(previous: Any, current: Any) -> Decimal | None:
    before = _money(previous)
    after = _money(current)
    if before is None or after is None:
        return None
    return after - before


def _plan_id(plan: Mapping[str, Any] | None) -> int | None:
    if not plan:
        return None
    value = plan.get("action_plan_id")
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _plan_fingerprint(plan: Mapping[str, Any] | None) -> str | None:
    if not plan:
        return None
    value = plan.get("decision_fingerprint")
    if isinstance(value, str) and len(value) == 64:
        return value
    # Live A5 output should contain its canonical fingerprint; this fallback is
    # only for defensive callers and deliberately excludes volatile IDs/times.
    stable = {
        key: value
        for key, value in plan.items()
        if key not in {"action_plan_id", "created_at", "generated_at"}
    }
    return _fingerprint(stable)


def _action_key(action: Mapping[str, Any], index: int) -> str:
    value = action.get("action_id")
    if value not in (None, ""):
        return str(value)
    return _fingerprint(
        {
            "index": index,
            "type": action.get("action_type"),
            "target": action.get("goal_id")
            or action.get("liability_id")
            or action.get("asset_id"),
            "owner": action.get("owner_user_id"),
        }
    )[:24]


def _actions(plan: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not plan:
        return {}
    raw = plan.get("actions")
    if not isinstance(raw, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        if isinstance(item, Mapping):
            value = deepcopy(dict(item))
            output[_action_key(value, index)] = value
    return output


def _stable_action(action: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in action.items()
        if key not in ACTION_IGNORED_FIELDS
    }


def _semantic(action: Mapping[str, Any] | None) -> str | None:
    if not action:
        return None
    action_type = str(action.get("action_type") or "").upper()
    return ACTION_TRANSITIONS.get(
        action_type, str(action.get("action_status") or action_type or "") or None
    )


def _max_materiality(*values: str) -> str:
    return max(values, key=lambda item: MATERIALITY_ORDER[item])


def _monetary_materiality(previous: Any, current: Any) -> str:
    before = _money(previous)
    after = _money(current)
    if before is None or after is None:
        return MONETARY_MATERIALITY["UNKNOWN_TRANSITION"]
    if abs(after - before) >= MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD:
        return MONETARY_MATERIALITY["AT_OR_ABOVE_THRESHOLD"]
    return MONETARY_MATERIALITY["BELOW_THRESHOLD"]


def _action_materiality(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> str:
    transition = (_semantic(before), _semantic(after))
    if transition in CRITICAL_TRANSITIONS:
        return "CRITICAL"
    if transition in HIGH_TRANSITIONS:
        return "HIGH"
    if before and not after and _semantic(before) == "BUY":
        return ACTION_REMOVED_BUY_MATERIALITY
    if (
        after
        and str(after.get("severity") or "").upper()
        in ACTION_CRITICAL_SEVERITIES
    ):
        return "CRITICAL"
    if before is None or after is None:
        return ACTION_ADD_REMOVE_MATERIALITY
    changed = {
        key
        for key in set(_stable_action(before)) | set(_stable_action(after))
        if _canonical_json(before.get(key)) != _canonical_json(after.get(key))
    }
    if changed & ACTION_MATERIAL_FIELDS:
        return "MEDIUM"
    if "amount" in changed:
        return _monetary_materiality(before.get("amount"), after.get("amount"))
    return ACTION_OTHER_CHANGE_MATERIALITY


def _category_for_action(
    action: Mapping[str, Any] | None,
    categories: Sequence[str],
) -> str:
    category = str((action or {}).get("category") or "").upper()
    preferred = ACTION_CATEGORY_PREFERENCES[
        "INVESTMENT" if category in {"INVESTMENT", "HOLD"} else "FINANCIAL"
    ]
    for item in preferred:
        if item in categories:
            return item
    return categories[0] if categories else "FRESHNESS"


def _change_id(payload: Mapping[str, Any]) -> str:
    return _fingerprint(payload)[:32]


def _change(
    *,
    change_type: str,
    category: str,
    entity_type: str,
    entity_id: Any,
    previous_value: Any,
    current_value: Any,
    materiality: str,
    reason: str,
    source: str,
    observed_at: datetime,
    as_of: datetime,
    previous_fingerprint: str | None,
    current_fingerprint: str | None,
    delta: Decimal | None = None,
    ownership_scope: str | None = None,
    owner_user_id: Any = None,
) -> dict[str, Any]:
    identity = {
        "change_type": change_type,
        "category": category,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "previous_value": previous_value,
        "current_value": current_value,
        "materiality": materiality,
        "source": source,
        "previous_fingerprint": previous_fingerprint,
        "current_fingerprint": current_fingerprint,
    }
    return {
        "change_id": _change_id(identity),
        **identity,
        "delta": delta,
        "delta_percent": None,
        "severity": CHANGE_SEVERITY_BY_MATERIALITY[materiality],
        "reason": reason,
        "observed_at": observed_at,
        "as_of": as_of,
        "ownership_scope": ownership_scope,
        "owner_user_id": owner_user_id,
    }


def _context_value(context: Mapping[str, Any] | None, *path: str) -> Any:
    value: Any = context
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _quality_value(context: Mapping[str, Any] | None) -> Any:
    value = _context_value(context, "state", "data_quality")
    if isinstance(value, Mapping):
        return value.get("status") or value.get("quality")
    return value


def _empty_diff(previous_id: int | None, current_id: int | None) -> dict[str, Any]:
    return {
        "previous_action_plan_id": previous_id,
        "current_action_plan_id": current_id,
        "added_actions": [],
        "removed_actions": [],
        "changed_actions": [],
        "unchanged_actions": [],
        "financial_delta": Decimal("0"),
        "investment_delta": Decimal("0"),
        "hold_cash_delta": Decimal("0"),
        "priority_changes": [],
        "status_change": None,
        "materiality": "NONE",
        "summary": "Nenhuma mudança relevante foi identificada.",
    }


def calculate_continuous_autopilot(
    previous_action_plan: Mapping[str, Any] | None,
    current_action_plan: Mapping[str, Any],
    *,
    as_of: datetime,
    observed_at: datetime | None = None,
    change_categories: Sequence[str] = (),
    reevaluation_scope: str | None = None,
    previous_context: Mapping[str, Any] | None = None,
    current_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare frozen A5 decisions without reimplementing any A1 -> A5 rule."""

    as_of = _utc(as_of)
    observed_at = _utc(observed_at or as_of)
    previous = deepcopy(dict(previous_action_plan)) if previous_action_plan else None
    current = deepcopy(dict(current_action_plan))
    household_id = current.get("household_id")
    if not isinstance(household_id, int) or isinstance(household_id, bool) or household_id <= 0:
        raise ValueError("current Action Plan requires a valid household_id")
    if previous is not None and previous.get("household_id") != household_id:
        raise ValueError("Action Plans from different households cannot be compared")

    categories = tuple(
        sorted(
            {
                str(item).upper()
                for item in change_categories
                if str(item).upper() in CHANGE_CATEGORIES
            }
        )
    )
    scope = reevaluation_scope or rules_reevaluation_scope(list(categories))
    if scope not in {"NONE", "FULL_CHAIN", "INVESTMENT_CHAIN"}:
        raise ValueError("invalid reevaluation scope")

    previous_id = _plan_id(previous)
    current_id = _plan_id(current)
    previous_fingerprint = _plan_fingerprint(previous)
    current_fingerprint = _plan_fingerprint(current)
    assert current_fingerprint is not None

    diff = _empty_diff(previous_id, current_id)
    changes: list[dict[str, Any]] = []
    materiality = "NONE"

    if previous is not None:
        before_actions = _actions(previous)
        after_actions = _actions(current)
        before_keys = set(before_actions)
        after_keys = set(after_actions)

        for key in sorted(after_keys - before_keys):
            action = after_actions[key]
            item_materiality = _action_materiality(None, action)
            diff["added_actions"].append(action)
            materiality = _max_materiality(materiality, item_materiality)
            changes.append(
                _change(
                    change_type="ACTION_ADDED",
                    category=_category_for_action(action, categories),
                    entity_type="ACTION_PLAN_ACTION",
                    entity_id=key,
                    previous_value=None,
                    current_value=_stable_action(action),
                    materiality=item_materiality,
                    reason="Uma nova ação apareceu no Action Plan canônico.",
                    source="action-plan-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                    ownership_scope=action.get("ownership_scope"),
                    owner_user_id=action.get("owner_user_id"),
                )
            )

        for key in sorted(before_keys - after_keys):
            action = before_actions[key]
            item_materiality = _action_materiality(action, None)
            diff["removed_actions"].append(action)
            materiality = _max_materiality(materiality, item_materiality)
            changes.append(
                _change(
                    change_type="ACTION_REMOVED",
                    category=_category_for_action(action, categories),
                    entity_type="ACTION_PLAN_ACTION",
                    entity_id=key,
                    previous_value=_stable_action(action),
                    current_value=None,
                    materiality=item_materiality,
                    reason="Uma ação deixou de fazer parte do Action Plan canônico.",
                    source="action-plan-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                    ownership_scope=action.get("ownership_scope"),
                    owner_user_id=action.get("owner_user_id"),
                )
            )

        for key in sorted(before_keys & after_keys):
            before = before_actions[key]
            after = after_actions[key]
            before_stable = _stable_action(before)
            after_stable = _stable_action(after)
            if _canonical_json(before_stable) == _canonical_json(after_stable):
                diff["unchanged_actions"].append(key)
                continue
            changed_fields = sorted(
                field
                for field in set(before_stable) | set(after_stable)
                if _canonical_json(before_stable.get(field))
                != _canonical_json(after_stable.get(field))
            )
            before_amount = before.get("amount")
            after_amount = after.get("amount")
            amount_delta = _money_delta(before_amount, after_amount)
            transition = {
                "previous": _semantic(before),
                "current": _semantic(after),
            }
            item_materiality = _action_materiality(before, after)
            changed = {
                "action_id": key,
                "before": before_stable,
                "after": after_stable,
                "changed_fields": changed_fields,
                "amount_delta": amount_delta,
                "transition": transition,
            }
            diff["changed_actions"].append(changed)
            if "priority_rank" in changed_fields:
                diff["priority_changes"].append(
                    {
                        "action_id": key,
                        "previous": before.get("priority_rank"),
                        "current": after.get("priority_rank"),
                    }
                )
            materiality = _max_materiality(materiality, item_materiality)
            changes.append(
                _change(
                    change_type="ACTION_CHANGED",
                    category=_category_for_action(after, categories),
                    entity_type="ACTION_PLAN_ACTION",
                    entity_id=key,
                    previous_value=before_stable,
                    current_value=after_stable,
                    delta=amount_delta if "amount" in changed_fields else None,
                    materiality=item_materiality,
                    reason="Uma ação canônica mudou de valor, ordem, status ou evidência.",
                    source="action-plan-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                    ownership_scope=after.get("ownership_scope"),
                    owner_user_id=after.get("owner_user_id"),
                )
            )

        diff["financial_delta"] = _money_delta(
            previous.get("total_financial_actions"),
            current.get("total_financial_actions"),
        )
        diff["investment_delta"] = _money_delta(
            previous.get("total_investment_actions"),
            current.get("total_investment_actions"),
        )
        diff["hold_cash_delta"] = _money_delta(
            previous.get("total_hold_cash"),
            current.get("total_hold_cash"),
        )
        if previous.get("status") != current.get("status"):
            diff["status_change"] = {
                "previous": previous.get("status"),
                "current": current.get("status"),
            }
            status_materiality = PLAN_STATUS_MATERIALITY.get(
                str(current.get("status") or "").upper(),
                PLAN_STATUS_MATERIALITY["DEFAULT"],
            )
            materiality = _max_materiality(materiality, status_materiality)
            changes.append(
                _change(
                    change_type="PLAN_STATUS_CHANGED",
                    category=categories[0] if categories else "DATA_QUALITY",
                    entity_type="ACTION_PLAN",
                    entity_id=current_id,
                    previous_value=previous.get("status"),
                    current_value=current.get("status"),
                    materiality=status_materiality,
                    reason="O estado do Action Plan mudou.",
                    source="action-plan-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        readiness_before = _context_value(
            previous_context, "policy", "investment_readiness"
        )
        readiness_after = _context_value(
            current_context, "policy", "investment_readiness"
        )
        if readiness_before is not None and readiness_before != readiness_after:
            readiness_materiality = (
                "CRITICAL"
                if (str(readiness_before), str(readiness_after))
                in CRITICAL_TRANSITIONS
                else READINESS_DEFAULT_MATERIALITY
            )
            materiality = _max_materiality(materiality, readiness_materiality)
            changes.append(
                _change(
                    change_type="INVESTMENT_READINESS_CHANGED",
                    category="POLICY",
                    entity_type="FINANCIAL_POLICY",
                    entity_id=current.get("financial_policy_decision_id"),
                    previous_value=readiness_before,
                    current_value=readiness_after,
                    materiality=readiness_materiality,
                    reason="A prontidão financeira para novos investimentos mudou.",
                    source="financial-policy-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        quality_before = _quality_value(previous_context)
        quality_after = _quality_value(current_context)
        if quality_before is not None and quality_before != quality_after:
            quality_materiality = DATA_QUALITY_MATERIALITY[
                "ADVERSE"
                if str(quality_after).upper() in DATA_QUALITY_ADVERSE
                else "DEFAULT"
            ]
            materiality = _max_materiality(materiality, quality_materiality)
            changes.append(
                _change(
                    change_type="DATA_QUALITY_CHANGED",
                    category="DATA_QUALITY",
                    entity_type="FINANCIAL_STATE",
                    entity_id=current.get("financial_state_snapshot_id"),
                    previous_value=quality_before,
                    current_value=quality_after,
                    materiality=quality_materiality,
                    reason="A qualidade dos dados usados pelo Financial State mudou.",
                    source="household-financial-state-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        policy_state_before = _context_value(
            previous_context, "policy", "policy_state"
        )
        policy_state_after = _context_value(current_context, "policy", "policy_state")
        if (
            policy_state_before is not None
            and policy_state_before != policy_state_after
        ):
            materiality = _max_materiality(
                materiality, POLICY_STATE_CHANGE_MATERIALITY
            )
            changes.append(
                _change(
                    change_type="POLICY_STATE_CHANGED",
                    category="POLICY",
                    entity_type="FINANCIAL_POLICY",
                    entity_id=current.get("financial_policy_decision_id"),
                    previous_value=policy_state_before,
                    current_value=policy_state_after,
                    materiality=POLICY_STATE_CHANGE_MATERIALITY,
                    reason="A prioridade definida pela Financial Policy mudou.",
                    source="financial-policy-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        allocation_status_before = _context_value(
            previous_context, "allocation", "allocation_status"
        )
        allocation_status_after = _context_value(
            current_context, "allocation", "allocation_status"
        )
        if (
            allocation_status_before is not None
            and allocation_status_before != allocation_status_after
        ):
            allocation_materiality = ALLOCATION_STATUS_MATERIALITY[
                "ADVERSE"
                if str(allocation_status_after).upper()
                in ALLOCATION_STATUS_ADVERSE
                else "DEFAULT"
            ]
            materiality = _max_materiality(materiality, allocation_materiality)
            changes.append(
                _change(
                    change_type="ALLOCATION_STATUS_CHANGED",
                    category="ALLOCATION",
                    entity_type="CAPITAL_ALLOCATION",
                    entity_id=current.get("capital_allocation_decision_id"),
                    previous_value=allocation_status_before,
                    current_value=allocation_status_after,
                    materiality=allocation_materiality,
                    reason="O estado da Capital Allocation mudou.",
                    source="capital-allocation-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        budget_before = _context_value(
            previous_context, "allocation", "investment_bucket_amount"
        )
        budget_after = _context_value(
            current_context, "allocation", "investment_bucket_amount"
        )
        if budget_before != budget_after and (
            budget_before is not None or budget_after is not None
        ):
            budget_delta = _money_delta(budget_before, budget_after)
            budget_materiality = _monetary_materiality(
                budget_before, budget_after
            )
            materiality = _max_materiality(materiality, budget_materiality)
            changes.append(
                _change(
                    change_type="INVESTMENT_BUCKET_CHANGED",
                    category="ALLOCATION",
                    entity_type="CAPITAL_ALLOCATION",
                    entity_id=current.get("capital_allocation_decision_id"),
                    previous_value=budget_before,
                    current_value=budget_after,
                    delta=budget_delta,
                    materiality=budget_materiality,
                    reason="O capital autorizado para investimento mudou.",
                    source="capital-allocation-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        orchestration_before = _context_value(
            previous_context, "orchestration", "status"
        )
        orchestration_after = _context_value(
            current_context, "orchestration", "status"
        )
        if orchestration_before is not None and orchestration_before != orchestration_after:
            orchestration_materiality = ORCHESTRATION_STATUS_MATERIALITY[
                "ADVERSE"
                if str(orchestration_after).upper()
                in ORCHESTRATION_STATUS_ADVERSE
                else "DEFAULT"
            ]
            materiality = _max_materiality(materiality, orchestration_materiality)
            changes.append(
                _change(
                    change_type="ORCHESTRATION_STATUS_CHANGED",
                    category="INVESTMENT_OPPORTUNITY",
                    entity_type="INVESTMENT_ORCHESTRATION",
                    entity_id=current.get("investment_orchestration_decision_id"),
                    previous_value=orchestration_before,
                    current_value=orchestration_after,
                    materiality=orchestration_materiality,
                    reason="A disponibilidade de oportunidades compatíveis mudou.",
                    source="investment-orchestrator-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

        if previous_fingerprint != current_fingerprint and not changes:
            materiality = FINGERPRINT_ONLY_MATERIALITY
            changes.append(
                _change(
                    change_type="PLAN_FINGERPRINT_CHANGED",
                    category=categories[0] if categories else "FRESHNESS",
                    entity_type="ACTION_PLAN",
                    entity_id=current_id,
                    previous_value=previous_fingerprint,
                    current_value=current_fingerprint,
                    materiality=FINGERPRINT_ONLY_MATERIALITY,
                    reason="Os inputs auditáveis mudaram sem alterar uma ação material.",
                    source="action-plan-v1",
                    observed_at=observed_at,
                    as_of=as_of,
                    previous_fingerprint=previous_fingerprint,
                    current_fingerprint=current_fingerprint,
                )
            )

    diff["materiality"] = materiality
    if previous is None:
        diff["summary"] = "O primeiro Action Plan foi registrado como baseline."
        status = INITIAL_STATUS_BY_ACTION_PLAN_STATUS.get(
            str(current.get("status") or "").upper(),
            INITIAL_STATUS_BY_ACTION_PLAN_STATUS["DEFAULT"],
        )
    elif materiality == "NONE":
        diff["summary"] = "Nenhuma mudança relevante foi identificada no plano."
        status = "UNCHANGED"
    else:
        diff["summary"] = f"{len(changes)} mudança(s) estruturada(s) foram identificadas."
        status = "CHANGED"

    alert_decision = ALERT_BY_MATERIALITY[materiality]
    alert: dict[str, Any] | None = None
    if alert_decision != "NO_ALERT":
        primary = max(changes, key=lambda item: MATERIALITY_ORDER[item["materiality"]])
        title = (
            "Ação financeira crítica"
            if alert_decision == "CRITICAL"
            else "Seu plano financeiro mudou"
        )
        summary = primary["reason"]
        recommended_action = (
            "Revise o novo plano antes de tomar outra decisão financeira."
            if alert_decision in {"IMPORTANT", "CRITICAL"}
            else "Consulte as mudanças e siga a nova ordem de ações."
        )
        alert_identity = {
            "household_id": household_id,
            "previous_fingerprint": previous_fingerprint,
            "current_fingerprint": current_fingerprint,
            "alert_decision": alert_decision,
            "primary_change": primary["change_id"],
        }
        alert = {
            "severity": alert_decision,
            "category": primary["category"],
            "title": title,
            "summary": summary,
            "what_changed": [item["reason"] for item in changes[:5]],
            "why_it_matters": "A mudança altera ações, segurança ou capital do plano atual.",
            "recommended_action": recommended_action,
            "previous_reference": {
                "action_plan_id": previous_id,
                "fingerprint": previous_fingerprint,
            },
            "current_reference": {
                "action_plan_id": current_id,
                "fingerprint": current_fingerprint,
            },
            "dedupe_key": _fingerprint(alert_identity),
        }

    identity = {
        "household_id": household_id,
        "previous_fingerprint": previous_fingerprint,
        "current_fingerprint": current_fingerprint,
        "scope": scope,
        "categories": categories,
        "diff": diff,
        "changes": changes,
        "ruleset_fingerprint": RULESET_FINGERPRINT,
    }
    decision_fingerprint = _fingerprint(identity)
    blockers = deepcopy(current.get("blockers") or [])
    warnings = deepcopy(current.get("warnings") or [])
    missing = deepcopy(current.get("missing_information") or [])
    return {
        "continuous_decision_id": None,
        "household_id": household_id,
        "previous_action_plan_id": previous_id,
        "current_action_plan_id": current_id,
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "status": status,
        "materiality": materiality,
        "alert_decision": alert_decision,
        "reevaluation_scope": scope,
        "change_categories": list(categories),
        "detected_changes": changes,
        "plan_diff": diff,
        "alert": alert,
        "blockers": blockers,
        "warnings": warnings,
        "missing_information": missing,
        "evidence": [
            {
                "code": "ACTION_PLAN_COMPARISON",
                "previous_action_plan_id": previous_id,
                "current_action_plan_id": current_id,
                "previous_fingerprint": previous_fingerprint,
                "current_fingerprint": current_fingerprint,
                "change_count": len(changes),
            }
        ],
        "rule_traces": [
            {
                "rule_id": "CAP-DEPENDENCY-GATE",
                "rule_version": RULES_VERSION,
                "outcome": scope,
                "observed_categories": list(categories),
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
        ],
        "ruleset": deepcopy(RULESET),
        "previous_fingerprint": previous_fingerprint,
        "current_fingerprint": current_fingerprint,
        "ruleset_fingerprint": RULESET_FINGERPRINT,
        "decision_fingerprint": decision_fingerprint,
        "dedupe_key": _fingerprint(
            {
                "household_id": household_id,
                "decision_fingerprint": decision_fingerprint,
            }
        ),
        "generated_at": as_of,
        "observed_at": observed_at,
        "created_at": None,
    }


compare_action_plans = calculate_continuous_autopilot
evaluate_continuous_autopilot = calculate_continuous_autopilot


def decision_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    return _fingerprint(
        {
            "household_id": payload.get("household_id"),
            "previous_fingerprint": payload.get("previous_fingerprint"),
            "current_fingerprint": payload.get("current_fingerprint"),
            "scope": payload.get("reevaluation_scope"),
            "categories": payload.get("change_categories") or [],
            "diff": payload.get("plan_diff") or {},
            "changes": payload.get("detected_changes") or [],
            "ruleset_fingerprint": payload.get("ruleset_fingerprint"),
        }
    )

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Final


ENGINE_VERSION: Final = "continuous-autopilot-v1"
RULES_VERSION: Final = "continuous-autopilot-rules-v1"

CHANGE_CATEGORIES: Final = (
    "FINANCIAL_DATA",
    "MARKET_DATA",
    "PROFILE",
    "GOALS",
    "DEBT",
    "ASSETS",
    "HOUSEHOLD",
    "POLICY",
    "ALLOCATION",
    "INVESTMENT_OPPORTUNITY",
    "DATA_QUALITY",
    "FRESHNESS",
)

FULL_CHAIN_CATEGORIES: Final = frozenset(
    {
        "FINANCIAL_DATA",
        "PROFILE",
        "GOALS",
        "DEBT",
        "ASSETS",
        "HOUSEHOLD",
        "POLICY",
        "ALLOCATION",
        "DATA_QUALITY",
        "FRESHNESS",
    }
)
INVESTMENT_CHAIN_CATEGORIES: Final = frozenset(
    {"MARKET_DATA", "INVESTMENT_OPPORTUNITY"}
)

MATERIALITY_ORDER: Final = {
    "NONE": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# All decision-affecting materiality rules live here so the frozen ruleset
# fingerprint changes whenever a threshold or precedence changes.
MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD: Final = Decimal("1.00")
MANUAL_FAILED_RETRY_COOLDOWN_SECONDS: Final = 60

ACTION_IGNORED_FIELDS: Final = frozenset({"generated_at"})
ACTION_TRANSITIONS: Final = {
    "INVESTMENT_BUY": "BUY",
    "INVESTMENT_WAIT": "WAIT",
    "INVESTMENT_AVOID": "AVOID",
}
ACTION_MATERIAL_FIELDS: Final = frozenset(
    {
        "action_type",
        "action_status",
        "priority_rank",
        "ownership_scope",
        "owner_user_id",
        "blockers",
    }
)
ACTION_CRITICAL_SEVERITIES: Final = frozenset({"CRITICAL"})
ACTION_ADD_REMOVE_MATERIALITY: Final = "MEDIUM"
ACTION_REMOVED_BUY_MATERIALITY: Final = "HIGH"
ACTION_OTHER_CHANGE_MATERIALITY: Final = "LOW"
MONETARY_MATERIALITY: Final = {
    "UNKNOWN_TRANSITION": "MEDIUM",
    "AT_OR_ABOVE_THRESHOLD": "MEDIUM",
    "BELOW_THRESHOLD": "LOW",
}

PLAN_STATUS_MATERIALITY: Final = {
    "BLOCKED": "CRITICAL",
    "PARTIAL": "HIGH",
    "DEFAULT": "MEDIUM",
}
READINESS_DEFAULT_MATERIALITY: Final = "HIGH"
DATA_QUALITY_ADVERSE: Final = frozenset(
    {"INSUFFICIENT", "INCONSISTENT", "STALE"}
)
DATA_QUALITY_MATERIALITY: Final = {"ADVERSE": "HIGH", "DEFAULT": "MEDIUM"}
POLICY_STATE_CHANGE_MATERIALITY: Final = "HIGH"
ALLOCATION_STATUS_ADVERSE: Final = frozenset({"BLOCKED", "CONSTRAINED"})
ALLOCATION_STATUS_MATERIALITY: Final = {
    "ADVERSE": "HIGH",
    "DEFAULT": "MEDIUM",
}
ORCHESTRATION_STATUS_ADVERSE: Final = frozenset(
    {"BLOCKED", "NO_SUITABLE_OPPORTUNITY"}
)
ORCHESTRATION_STATUS_MATERIALITY: Final = {
    "ADVERSE": "HIGH",
    "DEFAULT": "MEDIUM",
}
FINGERPRINT_ONLY_MATERIALITY: Final = "LOW"
CHANGE_SEVERITY_BY_MATERIALITY: Final = {
    "NONE": "INFO",
    "LOW": "INFO",
    "MEDIUM": "WARNING",
    "HIGH": "IMPORTANT",
    "CRITICAL": "CRITICAL",
}
ACTION_CATEGORY_PREFERENCES: Final = {
    "INVESTMENT": ("INVESTMENT_OPPORTUNITY", "MARKET_DATA", "PROFILE", "FRESHNESS"),
    "FINANCIAL": ("DEBT", "GOALS", "ASSETS", "FINANCIAL_DATA", "HOUSEHOLD"),
}
INITIAL_STATUS_BY_ACTION_PLAN_STATUS: Final = {
    "BLOCKED": "BLOCKED",
    "DEFAULT": "UP_TO_DATE",
}

ALERT_BY_MATERIALITY: Final = {
    "NONE": "NO_ALERT",
    # LOW is classified for audit but suppressed from the user inbox.
    "LOW": "INFORMATIONAL",
    "MEDIUM": "ACTION_RECOMMENDED",
    "HIGH": "IMPORTANT",
    "CRITICAL": "CRITICAL",
}

CRITICAL_TRANSITIONS: Final = frozenset(
    {
        ("BUY", "AVOID"),
        ("READY", "BLOCKED"),
    }
)
HIGH_TRANSITIONS: Final = frozenset(
    {
        ("BUY", "WAIT"),
        ("WAIT", "BUY"),
        ("NO_ACTION_REQUIRED", "BLOCKED"),
        ("READY", "PARTIAL"),
    }
)

RULESET: Final = {
    "engine_version": ENGINE_VERSION,
    "rules_version": RULES_VERSION,
    "dependency_graph": {
        "FULL_CHAIN": sorted(FULL_CHAIN_CATEGORIES),
        "INVESTMENT_CHAIN": sorted(INVESTMENT_CHAIN_CATEGORIES),
    },
    "materiality_order": MATERIALITY_ORDER,
    "alert_by_materiality": ALERT_BY_MATERIALITY,
    "critical_transitions": sorted([list(item) for item in CRITICAL_TRANSITIONS]),
    "high_transitions": sorted([list(item) for item in HIGH_TRANSITIONS]),
    "monetary_absolute_materiality_threshold": format(
        MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD, "f"
    ),
    "manual_failed_retry_cooldown_seconds": MANUAL_FAILED_RETRY_COOLDOWN_SECONDS,
    "action_ignored_fields": sorted(ACTION_IGNORED_FIELDS),
    "action_transitions": ACTION_TRANSITIONS,
    "action_material_fields": sorted(ACTION_MATERIAL_FIELDS),
    "action_critical_severities": sorted(ACTION_CRITICAL_SEVERITIES),
    "action_add_remove_materiality": ACTION_ADD_REMOVE_MATERIALITY,
    "action_removed_buy_materiality": ACTION_REMOVED_BUY_MATERIALITY,
    "action_other_change_materiality": ACTION_OTHER_CHANGE_MATERIALITY,
    "monetary_materiality": MONETARY_MATERIALITY,
    "plan_status_materiality": PLAN_STATUS_MATERIALITY,
    "readiness_default_materiality": READINESS_DEFAULT_MATERIALITY,
    "data_quality_adverse": sorted(DATA_QUALITY_ADVERSE),
    "data_quality_materiality": DATA_QUALITY_MATERIALITY,
    "policy_state_change_materiality": POLICY_STATE_CHANGE_MATERIALITY,
    "allocation_status_adverse": sorted(ALLOCATION_STATUS_ADVERSE),
    "allocation_status_materiality": ALLOCATION_STATUS_MATERIALITY,
    "orchestration_status_adverse": sorted(ORCHESTRATION_STATUS_ADVERSE),
    "orchestration_status_materiality": ORCHESTRATION_STATUS_MATERIALITY,
    "fingerprint_only_materiality": FINGERPRINT_ONLY_MATERIALITY,
    "change_severity_by_materiality": CHANGE_SEVERITY_BY_MATERIALITY,
    "action_category_preferences": {
        key: list(value) for key, value in ACTION_CATEGORY_PREFERENCES.items()
    },
    "initial_status_by_action_plan_status": INITIAL_STATUS_BY_ACTION_PLAN_STATUS,
    "low_alert_suppressed": True,
    "time_source": "explicit_as_of",
}

RULESET_FINGERPRINT: Final = hashlib.sha256(
    json.dumps(RULESET, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def reevaluation_scope(categories: tuple[str, ...] | list[str]) -> str:
    normalized = {str(item).upper() for item in categories}
    if normalized & FULL_CHAIN_CATEGORIES:
        return "FULL_CHAIN"
    if normalized & INVESTMENT_CHAIN_CATEGORIES:
        return "INVESTMENT_CHAIN"
    return "NONE"

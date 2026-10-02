from __future__ import annotations

import json
from copy import deepcopy

from backend.app.continuous_autopilot.privacy import (
    change_visible,
    project_decision_for_user,
)
from backend.app.continuous_autopilot.schemas import ContinuousAutopilotRead
from backend.tests.test_autopilot_continuous_engine import _evaluate, _plan


def _mixed_private_decision() -> dict:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    previous["actions"][1]["owner_user_id"] = 92
    previous["actions"][1]["description"] = "SEGREDO_92_ANTES"
    current["actions"][1].update(
        {
            "owner_user_id": 92,
            "action_type": "INVESTMENT_AVOID",
            "action_status": "AVOID",
            "description": "SEGREDO_92_DEPOIS",
        }
    )
    current["actions"][0]["amount"] = "700.00"
    current["total_financial_actions"] = "700.00"
    current["decision_fingerprint"] = "b" * 64
    return _evaluate(previous, current)


def test_shared_household_projection_hides_other_members_personal_change() -> None:
    canonical = _mixed_private_decision()
    frozen_copy = deepcopy(canonical)

    member_91 = project_decision_for_user(
        canonical, user_id=91, shared_household=True
    )
    member_92 = project_decision_for_user(
        canonical, user_id=92, shared_household=True
    )

    serialized_91 = json.dumps(member_91, default=str, sort_keys=True)
    serialized_92 = json.dumps(member_92, default=str, sort_keys=True)
    assert "SEGREDO_92" not in serialized_91
    assert '"owner_user_id": 92' not in serialized_91
    assert "SEGREDO_92" in serialized_92
    assert member_91["materiality"] == "MEDIUM"
    assert member_91["alert_decision"] == "ACTION_RECOMMENDED"
    assert member_91["plan_diff"]["financial_delta"] is None
    assert len(member_91["detected_changes"]) == 1
    assert len(member_91["plan_diff"]["changed_actions"]) == 1
    assert member_92["materiality"] == "CRITICAL"
    assert member_92["alert_decision"] == "CRITICAL"
    assert member_91["decision_fingerprint"] == canonical["decision_fingerprint"]
    assert canonical == frozen_copy
    ContinuousAutopilotRead.model_validate(member_91)
    ContinuousAutopilotRead.model_validate(member_92)


def test_personal_to_household_transfer_is_hidden_from_other_member() -> None:
    transfer = {
        "ownership_scope": "HOUSEHOLD",
        "owner_user_id": None,
        "previous_value": {
            "ownership_scope": "PERSONAL",
            "owner_user_id": 92,
            "description": "SEGREDO_92",
        },
        "current_value": {
            "ownership_scope": "HOUSEHOLD",
            "owner_user_id": None,
            "description": "Agora compartilhado",
        },
    }
    assert change_visible(transfer, recipient=91) is False
    assert change_visible(transfer, recipient=92) is True


def test_personal_household_projection_is_not_applied_to_individual_household() -> None:
    canonical = _mixed_private_decision()
    projected = project_decision_for_user(
        canonical, user_id=91, shared_household=False
    )
    assert projected == canonical
    assert projected is not canonical


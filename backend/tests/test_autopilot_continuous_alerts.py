from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.continuous_autopilot import alerts


NOW = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)


class _Scalars:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class _Session:
    def __init__(self, members):
        self.members = members

    async def execute(self, _query):
        return _Scalars(self.members)


def _payload(*, ownership_scope="HOUSEHOLD", owner_user_id=None, alert="IMPORTANT"):
    return {
        "status": "CHANGED",
        "materiality": "HIGH",
        "alert_decision": alert,
        "decision_fingerprint": "a" * 64,
        "previous_fingerprint": "b" * 64,
        "current_fingerprint": "c" * 64,
        "generated_at": NOW,
        "detected_changes": [
            {
                "change_id": "household-change",
                "ownership_scope": ownership_scope,
                "owner_user_id": owner_user_id,
                "materiality": "HIGH",
            }
        ],
        "plan_diff": {
            "status_change": {"previous": "READY", "current": "PARTIAL"},
            "summary": "Uma ação mudou.",
        },
        "alert": {
            "dedupe_key": "d" * 64,
            "summary": "Seu plano exige atenção.",
        },
    }


@pytest.mark.asyncio
async def test_household_alert_reuses_inbox_once_per_member(monkeypatch) -> None:
    inserted = []

    async def insert(_session, payload):
        inserted.append(payload)
        return True

    monkeypatch.setattr(alerts, "insert_alert_if_absent", insert)
    created = await alerts.deliver_continuous_alert(
        _Session([91, 92]),
        continuous_decision_id=51,
        household_id=10,
        payload=_payload(),
        alert_episode=1,
    )
    assert created == 2
    assert {item["user_id"] for item in inserted} == {91, 92}
    assert all(item["source_domain"] == "CONTINUOUS_AUTOPILOT" for item in inserted)
    assert all(item["decision_id"] is None and item["asset"] is None for item in inserted)
    assert len({item["deduplication_key"] for item in inserted}) == 2


@pytest.mark.asyncio
async def test_personal_alert_is_visible_only_to_owner(monkeypatch) -> None:
    inserted = []

    async def insert(_session, payload):
        inserted.append(payload)
        return True

    monkeypatch.setattr(alerts, "insert_alert_if_absent", insert)
    created = await alerts.deliver_continuous_alert(
        _Session([91, 92]),
        continuous_decision_id=51,
        household_id=10,
        payload=_payload(ownership_scope="PERSONAL", owner_user_id=92),
        alert_episode=1,
    )
    assert created == 1
    assert inserted[0]["user_id"] == 92
    assert inserted[0]["ownership_scope"] == "PERSONAL"
    assert inserted[0]["owner_user_id"] == 92


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["NO_ALERT", "INFORMATIONAL"])
async def test_suppressed_decision_does_not_query_or_write(
    monkeypatch, decision: str
) -> None:
    async def fail(*_args, **_kwargs):
        raise AssertionError("suppressed decisions must not touch the inbox")

    monkeypatch.setattr(alerts, "insert_alert_if_absent", fail)
    payload = _payload(alert=decision)
    if decision == "NO_ALERT":
        payload["alert"] = None
    assert await alerts.deliver_continuous_alert(
        _Session([]),
        continuous_decision_id=51,
        household_id=10,
        payload=payload,
        alert_episode=1,
    ) == 0


@pytest.mark.asyncio
async def test_mixed_personal_changes_are_partitioned_per_recipient(monkeypatch) -> None:
    inserted = []

    async def insert(_session, payload):
        inserted.append(payload)
        return True

    payload = _payload()
    payload["detected_changes"] = [
        {
            "change_id": "household-change",
            "ownership_scope": "HOUSEHOLD",
            "owner_user_id": None,
            "materiality": "MEDIUM",
            "reason": "A reserva compartilhada mudou.",
        },
        {
            "change_id": "personal-91",
            "ownership_scope": "PERSONAL",
            "owner_user_id": 91,
            "materiality": "HIGH",
            "reason": "A dívida pessoal de 91 mudou.",
        },
        {
            "change_id": "personal-92",
            "ownership_scope": "PERSONAL",
            "owner_user_id": 92,
            "materiality": "CRITICAL",
            "reason": "A dívida pessoal de 92 mudou.",
        },
    ]
    monkeypatch.setattr(alerts, "insert_alert_if_absent", insert)
    assert await alerts.deliver_continuous_alert(
        _Session([91, 92]),
        continuous_decision_id=51,
        household_id=10,
        payload=payload,
        alert_episode=3,
    ) == 2
    by_user = {item["user_id"]: item for item in inserted}
    assert "92" not in by_user[91]["message"]
    assert "91" not in by_user[92]["message"]
    assert all(item["ownership_scope"] == "HOUSEHOLD" for item in inserted)
    assert by_user[91]["severity"] == "HIGH"
    assert by_user[91]["current_state"]["materiality"] == "HIGH"
    assert by_user[92]["severity"] == "CRITICAL"
    assert by_user[92]["current_state"]["materiality"] == "CRITICAL"
    assert all(item["current_state"]["fingerprint"] is None for item in inserted)


@pytest.mark.asyncio
async def test_hidden_private_critical_does_not_promote_household_low_alert(
    monkeypatch,
) -> None:
    inserted = []

    async def insert(_session, payload):
        inserted.append(payload)
        return True

    payload = _payload()
    payload["detected_changes"] = [
        {
            "change_id": "shared-low",
            "ownership_scope": "HOUSEHOLD",
            "owner_user_id": None,
            "materiality": "LOW",
            "reason": "Mudanca compartilhada sem acao.",
        },
        {
            "change_id": "private-critical",
            "ownership_scope": "PERSONAL",
            "owner_user_id": 92,
            "materiality": "CRITICAL",
            "reason": "SEGREDO_92",
        },
    ]
    monkeypatch.setattr(alerts, "insert_alert_if_absent", insert)
    assert await alerts.deliver_continuous_alert(
        _Session([91, 92]),
        continuous_decision_id=51,
        household_id=10,
        payload=payload,
        alert_episode=4,
    ) == 1
    assert inserted[0]["user_id"] == 92
    assert inserted[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_alert_episode_changes_dedupe_key_after_resolution(monkeypatch) -> None:
    inserted = []

    async def insert(_session, payload):
        inserted.append(payload)
        return True

    monkeypatch.setattr(alerts, "insert_alert_if_absent", insert)
    for episode in (1, 1, 2):
        await alerts.deliver_continuous_alert(
            _Session([91]),
            continuous_decision_id=51,
            household_id=10,
            payload=_payload(),
            alert_episode=episode,
        )
    assert inserted[0]["deduplication_key"] == inserted[1]["deduplication_key"]
    assert inserted[2]["deduplication_key"] != inserted[0]["deduplication_key"]

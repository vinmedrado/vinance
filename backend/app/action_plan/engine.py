from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from backend.app.capital_allocation.engine import (
    decision_fingerprint_from_payload as allocation_fingerprint_from_payload,
)
from backend.app.capital_allocation.rules import (
    RULES_VERSION as ALLOCATION_RULES_VERSION,
)
from backend.app.financial_policy.engine import (
    decision_fingerprint_from_payload as policy_fingerprint_from_payload,
)
from backend.app.financial_policy.rules import RULES_VERSION as POLICY_RULES_VERSION
from backend.app.investment_orchestrator.engine import (
    decision_fingerprint_from_payload as orchestration_fingerprint_from_payload,
)
from backend.app.investment_orchestrator.rules import (
    RULES_VERSION as ORCHESTRATION_RULES_VERSION,
)
from backend.app.action_plan.rules import (
    ENGINE_VERSION,
    MONEY_QUANTUM,
    RULES,
    RULES_VERSION,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _sha256(value: Any) -> str:
    canonical = json.dumps(
        _json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _semantic(value: Mapping[str, Any], *excluded: str) -> dict[str, Any]:
    result = deepcopy(dict(value))
    for field in excluded:
        result.pop(field, None)
    return result


def decision_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    return _sha256(
        _semantic(
            payload,
            "action_plan_id",
            "financial_state_snapshot_id",
            "financial_policy_decision_id",
            "capital_allocation_decision_id",
            "investment_orchestration_decision_id",
            "decision_fingerprint",
            "created_at",
        )
    )


def _money(value: Any, *, allow_none: bool = False) -> Decimal | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError("monetary value is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("monetary value must be finite") from exc
    if not result.is_finite():
        raise ValueError("monetary value must be finite")
    return result.quantize(MONEY_QUANTUM)


def _as_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _message(
    code: str,
    message: str,
    *,
    fields: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "fields": list(fields),
        "rule_ids": list(rule_ids),
    }


def _normalise_message(raw: Mapping[str, Any], *, fallback_code: str) -> dict[str, Any]:
    return _message(
        str(raw.get("code") or fallback_code),
        str(raw.get("message") or raw.get("reason") or fallback_code),
        fields=tuple(str(item) for item in raw.get("fields") or []),
        rule_ids=tuple(str(item) for item in raw.get("rule_ids") or []),
    )


def _dedupe(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[dict[str, Any]] = []
    for raw in items:
        item = _normalise_message(raw, fallback_code="UNSPECIFIED")
        key = (item["code"], tuple(item["fields"]))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _trace(
    rule_id: str,
    description: str,
    outcome: str,
    observed: Mapping[str, Any],
    explanation: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_version": RULES_VERSION,
        "description": description,
        "outcome": outcome,
        "observed_values": dict(observed),
        "rule_parameters": {
            "period": RULES.period,
            "preserve_upstream_rounding": RULES.preserve_upstream_rounding,
        },
        "explanation": explanation,
    }


def _ruleset_fingerprint() -> str:
    return _sha256(RULES.payload())


def _state_fingerprint(state: Mapping[str, Any]) -> str:
    return _sha256(_semantic(state, "snapshot_id"))


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def _has_owner(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return bool(value.strip())
    return False


def _validate_chain(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    allocation: Mapping[str, Any],
    orchestration: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    expected_versions = (
        (state, "household-financial-state-v1", "STATE"),
        (policy, "financial-policy-v1", "POLICY"),
        (allocation, "capital-allocation-v1", "ALLOCATION"),
        (orchestration, "investment-orchestrator-v1", "ORCHESTRATION"),
    )
    for source, expected, label in expected_versions:
        if source.get("engine_version") != expected:
            blockers.append(
                _message(
                    f"{label}_VERSION_INVALID",
                    f"{label.title()} não usa a versão canônica esperada.",
                    fields=(f"{label.lower()}.engine_version",),
                    rule_ids=("APV1-CHAIN-001",),
                )
            )

    expected_rules_versions = (
        (policy, POLICY_RULES_VERSION, "POLICY"),
        (allocation, ALLOCATION_RULES_VERSION, "ALLOCATION"),
        (orchestration, ORCHESTRATION_RULES_VERSION, "ORCHESTRATION"),
    )
    for source, expected, label in expected_rules_versions:
        if source.get("rules_version") != expected:
            blockers.append(
                _message(
                    f"{label}_RULES_VERSION_INVALID",
                    f"{label.title()} não usa o ruleset canônico esperado.",
                    fields=(f"{label.lower()}.rules_version",),
                    rule_ids=("APV1-CHAIN-001",),
                )
            )

    if allocation.get("allocation_period") != RULES.period:
        blockers.append(
            _message(
                "ALLOCATION_PERIOD_MISMATCH",
                "O período da Capital Allocation não corresponde ao período do Action Plan.",
                fields=("capital_allocation.allocation_period",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    household_values = tuple(
        source.get("household_id")
        for source in (state, policy, allocation, orchestration)
    )
    household_ids = {value for value in household_values if value is not None}
    if any(value is None for value in household_values) or len(household_ids) != 1:
        blockers.append(
            _message(
                "HOUSEHOLD_CHAIN_MISMATCH",
                "As decisões não pertencem ao mesmo household.",
                fields=("household_id",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    state_ids = (
        state.get("snapshot_id"),
        policy.get("financial_state_snapshot_id"),
        allocation.get("financial_state_snapshot_id"),
        orchestration.get("financial_state_snapshot_id"),
    )
    present_state_ids = {value for value in state_ids if value is not None}
    if present_state_ids and (any(value is None for value in state_ids) or len(present_state_ids) != 1):
        blockers.append(
            _message(
                "STATE_CHAIN_MISMATCH",
                "A cadeia congelada aponta para Financial States diferentes.",
                fields=("financial_state_snapshot_id",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    policy_ids = (
        policy.get("policy_id"),
        allocation.get("financial_policy_id"),
        orchestration.get("financial_policy_decision_id"),
    )
    present_policy_ids = {value for value in policy_ids if value is not None}
    if present_policy_ids and (any(value is None for value in policy_ids) or len(present_policy_ids) != 1):
        blockers.append(
            _message(
                "POLICY_CHAIN_MISMATCH",
                "A cadeia congelada aponta para Financial Policies diferentes.",
                fields=("financial_policy_decision_id",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    allocation_ids = (
        allocation.get("allocation_id"),
        orchestration.get("capital_allocation_decision_id"),
    )
    if (allocation_ids[0] is None) != (allocation_ids[1] is None) or (
        allocation_ids[0] is not None and allocation_ids[0] != allocation_ids[1]
    ):
        blockers.append(
            _message(
                "ALLOCATION_CHAIN_MISMATCH",
                "A Orchestration não referencia a Capital Allocation informada.",
                fields=("capital_allocation_decision_id",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    persistence_ids = (
        state.get("snapshot_id"),
        policy.get("policy_id"),
        allocation.get("allocation_id"),
        orchestration.get("orchestration_id"),
    )
    if any(value is None for value in persistence_ids) and any(
        value is not None for value in persistence_ids
    ):
        blockers.append(
            _message(
                "CHAIN_PERSISTENCE_MODE_MISMATCH",
                "A cadeia precisa ser inteiramente live ou inteiramente congelada.",
                fields=(
                    "financial_state_snapshot_id",
                    "financial_policy_decision_id",
                    "capital_allocation_decision_id",
                    "investment_orchestration_decision_id",
                ),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    policy_digest = policy.get("decision_fingerprint")
    allocation_digest = allocation.get("decision_fingerprint")
    orchestration_digest = orchestration.get("decision_fingerprint")
    for digest, label in (
        (policy_digest, "POLICY"),
        (allocation_digest, "ALLOCATION"),
        (orchestration_digest, "ORCHESTRATION"),
    ):
        if not _is_sha256(digest):
            blockers.append(
                _message(
                    f"{label}_FINGERPRINT_REQUIRED",
                    f"{label.title()} não possui fingerprint SHA-256 canônico.",
                    fields=(f"{label.lower()}.decision_fingerprint",),
                    rule_ids=("APV1-CHAIN-001",),
                )
            )
    if _is_sha256(policy_digest) and policy_fingerprint_from_payload(policy) != policy_digest:
        blockers.append(
            _message(
                "POLICY_FINGERPRINT_INVALID",
                "O fingerprint da Financial Policy não confere.",
                fields=("financial_policy.decision_fingerprint",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )
    if (
        _is_sha256(allocation_digest)
        and allocation_fingerprint_from_payload(allocation) != allocation_digest
    ):
        blockers.append(
            _message(
                "ALLOCATION_FINGERPRINT_INVALID",
                "O fingerprint da Capital Allocation não confere.",
                fields=("capital_allocation.decision_fingerprint",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )
    if (
        _is_sha256(orchestration_digest)
        and orchestration_fingerprint_from_payload(orchestration)
        != orchestration_digest
    ):
        blockers.append(
            _message(
                "ORCHESTRATION_FINGERPRINT_INVALID",
                "O fingerprint da Investment Orchestration não confere.",
                fields=("investment_orchestration.decision_fingerprint",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    state_digest = _state_fingerprint(state)
    comparisons = (
        (allocation.get("input_fingerprint"), state_digest, "STATE_ALLOCATION_FINGERPRINT_MISMATCH"),
        (allocation.get("policy_fingerprint"), policy_digest, "POLICY_ALLOCATION_FINGERPRINT_MISMATCH"),
        (orchestration.get("state_fingerprint"), state_digest, "STATE_ORCHESTRATION_FINGERPRINT_MISMATCH"),
        (orchestration.get("policy_fingerprint"), policy_digest, "POLICY_ORCHESTRATION_FINGERPRINT_MISMATCH"),
        (orchestration.get("allocation_fingerprint"), allocation_digest, "ALLOCATION_ORCHESTRATION_FINGERPRINT_MISMATCH"),
    )
    for observed, expected, code in comparisons:
        if observed != expected:
            blockers.append(
                _message(
                    code,
                    "A cadeia de fingerprints não representa as mesmas decisões congeladas.",
                    fields=("decision_fingerprint",),
                    rule_ids=("APV1-CHAIN-001",),
                )
            )

    currency_values = (allocation.get("currency"), orchestration.get("currency"))
    currencies = {
        str(value).upper()
        for value in currency_values
        if value
    }
    if any(not value for value in currency_values) or len(currencies) != 1:
        blockers.append(
            _message(
                "CURRENCY_CHAIN_MISMATCH",
                "Allocation e Orchestration usam moedas incompatíveis.",
                fields=("currency",),
                rule_ids=("APV1-CHAIN-001",),
            )
        )

    investment_budget = _money(orchestration.get("investment_budget"), allow_none=True)
    investment_bucket = _money(allocation.get("investment_bucket_amount"), allow_none=True)
    suggested = _money(orchestration.get("suggested_capital"), allow_none=True)
    remaining = _money(orchestration.get("remaining_investment_cash"), allow_none=True)
    if investment_budget is None or investment_bucket is None or investment_budget != investment_bucket:
        blockers.append(
            _message(
                "INVESTMENT_BUDGET_MISMATCH",
                "O budget de investimento não corresponde ao valor autorizado pela Allocation.",
                fields=("investment_budget",),
                rule_ids=("APV1-CHAIN-001", "APV1-CONSERVATION-001"),
            )
        )
    if suggested is None or remaining is None or investment_budget is None or suggested + remaining != investment_budget:
        blockers.append(
            _message(
                "ORCHESTRATION_CONSERVATION_INVALID",
                "Capital sugerido e caixa preservado não reconciliam o investment budget.",
                fields=("suggested_capital", "remaining_investment_cash"),
                rule_ids=("APV1-CHAIN-001", "APV1-CONSERVATION-001"),
            )
        )
    speculative = _money(orchestration.get("speculative_capital"), allow_none=True)
    if speculative != Decimal("0.00") or orchestration.get("trading_dispatch") is not False:
        blockers.append(
            _message(
                "TRADING_ISOLATION_INVALID",
                "A cadeia viola a separação obrigatória do Trading.",
                fields=("speculative_capital", "trading_dispatch"),
                rule_ids=("APV1-TRADING-001",),
            )
        )
    for index, item in enumerate(allocation.get("allocations") or []):
        if not isinstance(item, Mapping):
            continue
        scope = item.get("ownership_scope")
        owner_user_id = item.get("user_id")
        if scope == "PERSONAL" and not _has_owner(owner_user_id):
            blockers.append(
                _message(
                    "PERSONAL_OWNER_REQUIRED",
                    "Uma alocação pessoal precisa identificar inequivocamente o usuário proprietário.",
                    fields=(f"capital_allocation.allocations.{index}.user_id",),
                    rule_ids=("APV1-OWNERSHIP-001",),
                )
            )
        if scope is None and _has_owner(owner_user_id):
            blockers.append(
                _message(
                    "OWNERSHIP_SCOPE_REQUIRED",
                    "Uma alocação com usuário proprietário precisa declarar o ownership scope.",
                    fields=(f"capital_allocation.allocations.{index}.ownership_scope",),
                    rule_ids=("APV1-OWNERSHIP-001",),
                )
            )
    return _dedupe(blockers)


def _action(
    *,
    action_id: str,
    category: str,
    action_type: str,
    rank: int,
    title: str,
    description: str,
    household_id: int,
    generated_at: datetime,
    source_engine: str,
    source_decision_id: Any,
    source_reference: Mapping[str, Any],
    ownership_scope: str | None = None,
    owner_user_id: Any = None,
    currency: str | None = None,
    amount: Decimal | None = None,
    target_amount: Decimal | None = None,
    remaining_need: Decimal | None = None,
    liability_id: Any = None,
    goal_id: Any = None,
    asset_id: int | None = None,
    symbol: str | None = None,
    asset_class: str | None = None,
    quantity_candidate: int | None = None,
    price_reference: Decimal | None = None,
    price_timestamp: datetime | None = None,
    price_source: str | None = None,
    freshness_status: str | None = None,
    action_status: str,
    severity: str,
    reason: str,
    evidence: Sequence[Any] = (),
    warnings: Sequence[Any] = (),
    blockers: Sequence[Any] = (),
    missing_information: Sequence[Any] = (),
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "category": category,
        "action_type": action_type,
        "priority_rank": rank,
        "title": title,
        "description": description,
        "ownership_scope": ownership_scope,
        "owner_user_id": owner_user_id,
        "household_id": household_id,
        "currency": currency,
        "amount": amount,
        "target_amount": target_amount,
        "remaining_need": remaining_need,
        "liability_id": liability_id,
        "goal_id": goal_id,
        "asset_id": asset_id,
        "symbol": symbol,
        "asset_class": asset_class,
        "quantity_candidate": quantity_candidate,
        "price_reference": price_reference,
        "price_timestamp": price_timestamp,
        "price_source": price_source,
        "freshness_status": freshness_status,
        "action_status": action_status,
        "severity": severity,
        "reason": reason,
        "evidence": list(evidence),
        "warnings": list(warnings),
        "blockers": list(blockers),
        "missing_information": list(missing_information),
        "source_engine": source_engine,
        "source_decision_id": source_decision_id,
        "source_reference": dict(source_reference),
        "generated_at": generated_at,
    }


def _financial_actions(
    allocation: Mapping[str, Any],
    *,
    household_id: int,
    currency: str | None,
    generated_at: datetime,
) -> list[dict[str, Any]]:
    type_map = {
        "DATA": ("INFORMATION", "COMPLETE_INFORMATION", "Complete as informações financeiras"),
        "CASH_FLOW": ("FINANCIAL", "STABILIZE_CASHFLOW", "Estabilize seu fluxo de caixa"),
        "LIABILITY": ("FINANCIAL", "DEBT_PAYMENT", "Reduza a dívida priorizada"),
        "EMERGENCY_RESERVE": ("FINANCIAL", "EMERGENCY_RESERVE_CONTRIBUTION", "Fortaleça sua reserva"),
        "GOAL": ("FINANCIAL", "GOAL_CONTRIBUTION", "Avance no objetivo financeiro"),
    }
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(allocation.get("allocations") or [], start=1):
        if not isinstance(raw, Mapping):
            continue
        target_type = str(raw.get("target_type") or "").upper()
        if target_type not in type_map:
            continue
        category, action_type, default_title = type_map[target_type]
        rank = int(raw.get("priority_rank") or index)
        allocated = _money(raw.get("allocated_amount"), allow_none=True)
        requested = _money(raw.get("requested_amount"), allow_none=True)
        remaining = _money(raw.get("remaining_need"), allow_none=True)
        status = str(raw.get("status") or "BLOCKED").upper()
        action_status = (
            "INFORMATIONAL"
            if category == "INFORMATION"
            else ("ACTIONABLE" if allocated is not None and allocated > 0 else "BLOCKED")
        )
        target_name = raw.get("target_name")
        title = str(target_name or default_title)
        target_id = raw.get("target_id")
        result.append(
            _action(
                action_id=f"allocation-{rank:03d}-{action_type.lower()}-{target_id or index}",
                category=category,
                action_type=action_type,
                rank=rank,
                title=title,
                description=str(raw.get("reason") or default_title),
                household_id=household_id,
                generated_at=generated_at,
                source_engine="capital-allocation-v1",
                source_decision_id=allocation.get("allocation_id"),
                source_reference={
                    "priority_code": raw.get("priority_code"),
                    "target_type": target_type,
                    "target_id": target_id,
                    "allocation_status": status,
                },
                ownership_scope=raw.get("ownership_scope"),
                owner_user_id=raw.get("user_id"),
                currency=(None if category == "INFORMATION" else currency),
                amount=(None if category == "INFORMATION" else allocated),
                target_amount=requested,
                remaining_need=remaining,
                liability_id=(target_id if target_type == "LIABILITY" else None),
                goal_id=(target_id if target_type == "GOAL" else None),
                action_status=action_status,
                severity=("INFO" if action_status in {"ACTIONABLE", "INFORMATIONAL"} else "WARNING"),
                reason=str(raw.get("reason") or "Decisão herdada da Capital Allocation."),
                evidence=raw.get("evidence_refs") or [],
            )
        )
    return result


def _information_actions(
    policy: Mapping[str, Any],
    allocation: Mapping[str, Any],
    orchestration: Mapping[str, Any],
    *,
    household_id: int,
    generated_at: datetime,
    starting_rank: int,
) -> list[dict[str, Any]]:
    messages: list[tuple[str, Any, Mapping[str, Any]]] = []
    for source_engine, source in (
        ("financial-policy-v1", policy),
        ("capital-allocation-v1", allocation),
        ("investment-orchestrator-v1", orchestration),
    ):
        for raw in source.get("missing_information") or []:
            if isinstance(raw, Mapping):
                messages.append((source_engine, source, raw))
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[dict[str, Any]] = []
    for source_engine, source, raw in messages:
        code = str(raw.get("code") or "COMPLETE_INFORMATION")
        fields = tuple(str(item) for item in raw.get("fields") or [])
        key = (code, fields)
        if key in seen:
            continue
        seen.add(key)
        rank = starting_rank + len(result)
        source_id = (
            source.get("policy_id")
            or source.get("allocation_id")
            or source.get("orchestration_id")
        )
        result.append(
            _action(
                action_id=f"information-{rank:03d}-{code.lower()}",
                category="INFORMATION",
                action_type="COMPLETE_INFORMATION",
                rank=rank,
                title="Complete uma informação importante",
                description=str(raw.get("message") or code),
                household_id=household_id,
                generated_at=generated_at,
                source_engine=source_engine,
                source_decision_id=source_id,
                source_reference={"code": code, "fields": list(fields)},
                action_status="INFORMATIONAL",
                severity="WARNING",
                reason=str(raw.get("message") or code),
                missing_information=[dict(raw)],
            )
        )
    return result


def _investment_actions(
    orchestration: Mapping[str, Any],
    *,
    household_id: int,
    currency: str | None,
    ownership_scope: str | None,
    owner_user_id: Any,
    generated_at: datetime,
    starting_rank: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(orchestration.get("ranked_opportunities") or [], start=1):
        if not isinstance(raw, Mapping):
            continue
        upstream_action = str(raw.get("action") or "NO_RECOMMENDATION").upper()
        guardrail = str(raw.get("guardrail_status") or "UNKNOWN").upper()
        if guardrail == "BLOCKED":
            upstream_action = "AVOID"
        elif guardrail == "WARNING" and upstream_action == "BUY":
            upstream_action = "WAIT"
        action_type = {
            "BUY": "INVESTMENT_BUY",
            "AVOID": "INVESTMENT_AVOID",
        }.get(upstream_action, "INVESTMENT_WAIT")
        action_status = {
            "INVESTMENT_BUY": "ACTIONABLE",
            "INVESTMENT_AVOID": "AVOID",
            "INVESTMENT_WAIT": "WAIT",
        }[action_type]
        capital = _money(raw.get("capital_committed"), allow_none=True)
        if action_type != "INVESTMENT_BUY":
            capital = None
        elif capital is None or capital <= 0:
            action_type = "INVESTMENT_WAIT"
            action_status = "WAIT"
            capital = None
        quantity_raw = raw.get("quantity_suggested", raw.get("quantity_candidate"))
        try:
            quantity = int(quantity_raw) if quantity_raw is not None else None
        except (TypeError, ValueError):
            quantity = None
        rank = starting_rank + len(result)
        symbol = str(raw.get("ticker") or raw.get("symbol") or "Oportunidade")
        result.append(
            _action(
                action_id=f"orchestration-{rank:03d}-{action_type.lower()}-{raw.get('asset_id') or symbol}",
                category="INVESTMENT",
                action_type=action_type,
                rank=rank,
                title=symbol,
                description=str(raw.get("reason") or "Decisão herdada do Investment Orchestrator."),
                household_id=household_id,
                generated_at=generated_at,
                source_engine="investment-orchestrator-v1",
                source_decision_id=orchestration.get("orchestration_id"),
                source_reference={
                    "opportunity_rank": raw.get("rank"),
                    "guardrail_status": guardrail,
                    "recommendation_score": raw.get("recommendation_score"),
                    "market": raw.get("market"),
                },
                ownership_scope=ownership_scope,
                owner_user_id=owner_user_id,
                currency=currency,
                amount=capital,
                asset_id=raw.get("asset_id"),
                symbol=symbol,
                asset_class=raw.get("asset_class"),
                quantity_candidate=quantity,
                price_reference=_money(raw.get("price_reference"), allow_none=True),
                price_timestamp=_as_datetime(raw.get("data_timestamp")),
                price_source=raw.get("price_source"),
                freshness_status=raw.get("freshness_status"),
                action_status=action_status,
                severity=("INFO" if action_status == "ACTIONABLE" else "WARNING"),
                reason=str(raw.get("reason") or upstream_action),
                evidence=raw.get("reasons") or [],
                warnings=raw.get("warnings") or [],
                blockers=(raw.get("reasons") or [] if action_status == "AVOID" else []),
            )
        )

    if (
        str(orchestration.get("status") or "").upper() == "NO_SUITABLE_OPPORTUNITY"
        and not result
    ):
        rank = starting_rank + len(result)
        result.append(
            _action(
                action_id=f"orchestration-{rank:03d}-investment-wait",
                category="INVESTMENT",
                action_type="INVESTMENT_WAIT",
                rank=rank,
                title="Não realizar novo investimento agora",
                description="Nenhuma oportunidade passou pelos critérios atuais.",
                household_id=household_id,
                generated_at=generated_at,
                source_engine="investment-orchestrator-v1",
                source_decision_id=orchestration.get("orchestration_id"),
                source_reference={"status": "NO_SUITABLE_OPPORTUNITY"},
                ownership_scope=ownership_scope,
                owner_user_id=owner_user_id,
                currency=currency,
                action_status="WAIT",
                severity="INFO",
                reason="Capital disponível não cria obrigação de compra.",
            )
        )
    return result


def calculate_action_plan(
    financial_state: Mapping[str, Any],
    financial_policy: Mapping[str, Any],
    capital_allocation: Mapping[str, Any],
    investment_orchestration: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert an exact frozen A1 -> A4 chain into an immutable action plan."""

    state = deepcopy(dict(financial_state))
    policy = deepcopy(dict(financial_policy))
    allocation = deepcopy(dict(capital_allocation))
    orchestration = deepcopy(dict(investment_orchestration))
    generated_at = (
        _as_datetime(orchestration.get("generated_at"))
        or _as_datetime(allocation.get("generated_at"))
        or _as_datetime(policy.get("generated_at"))
        or _as_datetime(state.get("evaluated_at"))
    )
    if generated_at is None:
        raise ValueError("the canonical chain must provide a deterministic timestamp")

    chain_blockers = _validate_chain(state, policy, allocation, orchestration)
    upstream_blockers = _dedupe(
        item
        for source in (policy, allocation, orchestration)
        for item in source.get("blockers") or []
        if isinstance(item, Mapping)
    )
    blockers = _dedupe([*chain_blockers, *upstream_blockers])
    warnings = _dedupe(
        item
        for source in (policy, allocation, orchestration)
        for collection in (source.get("warnings") or [], source.get("limitations") or [])
        for item in collection
        if isinstance(item, Mapping)
    )
    missing_information = _dedupe(
        item
        for source in (policy, allocation, orchestration)
        for item in source.get("missing_information") or []
        if isinstance(item, Mapping)
    )
    household_id = int(state.get("household_id") or 0)
    currency_value = allocation.get("currency") or orchestration.get("currency")
    currency = str(currency_value).upper() if currency_value else None
    period = (
        RULES.period
        if allocation.get("allocation_period") == RULES.period
        else None
    )
    investment_allocation = next(
        (
            item
            for item in allocation.get("allocations") or []
            if isinstance(item, Mapping)
            and str(item.get("target_type") or "").upper() == "INVESTMENT"
        ),
        {},
    )
    investment_ownership_scope = investment_allocation.get("ownership_scope")
    investment_owner_user_id = investment_allocation.get("user_id")

    actions: list[dict[str, Any]] = []
    if not chain_blockers:
        financial = _financial_actions(
            allocation,
            household_id=household_id,
            currency=currency,
            generated_at=generated_at,
        )
        actions.extend(financial)
        actions.extend(
            _information_actions(
                policy,
                allocation,
                orchestration,
                household_id=household_id,
                generated_at=generated_at,
                starting_rank=max((item["priority_rank"] for item in actions), default=0) + 1,
            )
        )
        actions.extend(
            _investment_actions(
                orchestration,
                household_id=household_id,
                currency=currency,
                ownership_scope=investment_ownership_scope,
                owner_user_id=investment_owner_user_id,
                generated_at=generated_at,
                starting_rank=max((item["priority_rank"] for item in actions), default=0) + 1,
            )
        )
        remaining = _money(orchestration.get("remaining_investment_cash"), allow_none=True)
        if remaining is not None and remaining > 0:
            rank = max((item["priority_rank"] for item in actions), default=0) + 1
            actions.append(
                _action(
                    action_id=f"orchestration-{rank:03d}-hold-cash",
                    category="HOLD",
                    action_type="HOLD_CASH",
                    rank=rank,
                    title="Mantenha o capital restante em caixa",
                    description="O capital não comprometido permanece preservado neste plano.",
                    household_id=household_id,
                    generated_at=generated_at,
                    source_engine="investment-orchestrator-v1",
                    source_decision_id=orchestration.get("orchestration_id"),
                    source_reference={
                        "status": orchestration.get("status"),
                        "remaining_investment_cash": remaining,
                    },
                    ownership_scope=investment_ownership_scope,
                    owner_user_id=investment_owner_user_id,
                    currency=currency,
                    amount=remaining,
                    action_status="WAIT",
                    severity="INFO",
                    reason=(
                        "Nenhuma oportunidade adicional passou pelos critérios atuais."
                        if orchestration.get("status") == "NO_SUITABLE_OPPORTUNITY"
                        else "O Orchestrator preservou este valor sem compromisso de compra."
                    ),
                )
            )

    information_actions = [item for item in actions if item["category"] == "INFORMATION"]
    financial_actions = [item for item in actions if item["category"] == "FINANCIAL"]
    investment_actions = [item for item in actions if item["category"] == "INVESTMENT"]
    hold_actions = [item for item in actions if item["category"] == "HOLD"]

    total_financial = sum(
        (item["amount"] or Decimal("0.00") for item in financial_actions),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM)
    total_investment = sum(
        (
            item["amount"] or Decimal("0.00")
            for item in investment_actions
            if item["action_type"] == "INVESTMENT_BUY"
        ),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM)
    total_hold = sum(
        (item["amount"] or Decimal("0.00") for item in hold_actions),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM)
    allocation_rows = allocation.get("allocations")
    authorized_financial = (
        sum(
            (
                _money(item.get("allocated_amount"), allow_none=True)
                or Decimal("0.00")
                for item in allocation_rows
                if isinstance(item, Mapping)
                and str(item.get("target_type") or "").upper()
                not in {"DATA", "INVESTMENT"}
            ),
            Decimal("0.00"),
        ).quantize(MONEY_QUANTUM)
        if isinstance(allocation_rows, list)
        else None
    )
    investment_budget = _money(
        orchestration.get("investment_budget"), allow_none=True
    )
    suggested = _money(orchestration.get("suggested_capital"), allow_none=True)
    if authorized_financial is not None and total_financial > authorized_financial:
        raise AssertionError("financial actions exceeded the authorized allocation")
    if suggested is not None and total_investment > suggested:
        raise AssertionError("investment actions exceeded suggested capital")
    if (
        investment_budget is not None
        and total_investment + total_hold > investment_budget
    ):
        raise AssertionError("BUY plus HOLD exceeded the investment budget")

    upstream_blocked = any(
        str(source.get(key) or "").upper() in {"DATA_BLOCKED", "BLOCKED"}
        for source, key in (
            (policy, "policy_state"),
            (allocation, "allocation_status"),
            (orchestration, "status"),
        )
    )
    if chain_blockers:
        status = "BLOCKED"
    elif upstream_blocked:
        # Critical gates from Policy, Allocation or Orchestration remain
        # authoritative even when the plan can still explain safe next steps.
        status = "BLOCKED"
    elif not actions:
        status = "NO_ACTION_REQUIRED"
        actions.append(
            _action(
                action_id="plan-001-no-action",
                category="INFORMATION",
                action_type="NO_ACTION",
                rank=1,
                title="Nenhuma ação nova é necessária",
                description="A cadeia válida não exige ação concreta neste período.",
                household_id=household_id,
                generated_at=generated_at,
                source_engine=ENGINE_VERSION,
                source_decision_id=None,
                source_reference={},
                action_status="NO_ACTION",
                severity="INFO",
                reason="Nenhuma decisão anterior produziu uma ação para o período.",
            )
        )
        information_actions = list(actions)
    elif upstream_blocked or missing_information or information_actions:
        status = "PARTIAL"
    else:
        status = "READY"

    # Python's sort is stable: equal upstream ranks retain the exact Allocation
    # / Orchestration order instead of being reordered by an implementation ID.
    actions.sort(key=lambda item: int(item["priority_rank"]))
    for position, item in enumerate(actions, start=1):
        item["priority_rank"] = position
    # Category views are projections of the final canonical ordering, not
    # independently ordered copies.
    information_actions = [item for item in actions if item["category"] == "INFORMATION"]
    financial_actions = [item for item in actions if item["category"] == "FINANCIAL"]
    investment_actions = [item for item in actions if item["category"] == "INVESTMENT"]
    hold_actions = [item for item in actions if item["category"] == "HOLD"]

    evidence = [
        {
            "code": "AUTHORIZED_FINANCIAL_CAPITAL",
            "label": "Capital autorizado para prioridades financeiras",
            "value": authorized_financial,
            "unit": currency,
            "source": "capital_allocation.allocations",
        },
        {
            "code": "AUTHORIZED_INVESTMENT_CAPITAL",
            "label": "Capital autorizado para investimentos",
            "value": investment_budget,
            "unit": currency,
            "source": "investment_orchestration.investment_budget",
        },
        {
            "code": "INVESTMENT_BUY_TOTAL",
            "label": "Capital representado em ações BUY",
            "value": total_investment,
            "unit": currency,
            "source": "action_plan.investment_actions",
        },
        {
            "code": "HOLD_CASH_TOTAL",
            "label": "Capital preservado em caixa",
            "value": total_hold,
            "unit": currency,
            "source": "action_plan.hold_actions",
        },
    ]
    traces = [
        _trace(
            "APV1-CHAIN-001",
            "Valida a cadeia canônica completa.",
            "TRIGGERED" if chain_blockers else "NOT_TRIGGERED",
            {"blocker_count": len(chain_blockers)},
            "IDs, household, versões, fingerprints, moeda e budgets foram reconciliados.",
        ),
        _trace(
            "APV1-INFORMATION-001",
            "Converte informação ausente em ação não monetária.",
            "TRIGGERED" if information_actions else "NOT_TRIGGERED",
            {"action_count": len(information_actions)},
            "Ausência permaneceu explícita e nunca foi transformada em zero.",
        ),
        _trace(
            "APV1-FINANCIAL-001",
            "Representa valores exatos da Capital Allocation.",
            "TRIGGERED" if financial_actions else "NOT_TRIGGERED",
            {"authorized": authorized_financial, "represented": total_financial},
            "O plano não recalculou prioridades ou valores financeiros.",
        ),
        _trace(
            "APV1-INVESTMENT-001",
            "Preserva BUY, WAIT e AVOID do Orchestrator.",
            "TRIGGERED" if investment_actions else "NOT_TRIGGERED",
            {"buy_total": total_investment, "suggested_capital": suggested},
            "Guardrails prevaleceram e somente BUY comprometeu capital.",
        ),
        _trace(
            "APV1-HOLD-001",
            "Expõe caixa de investimento preservado.",
            "TRIGGERED" if hold_actions else "NOT_TRIGGERED",
            {"hold_cash": total_hold},
            "Capital não utilizado permaneceu visível no plano.",
        ),
        _trace(
            "APV1-OWNERSHIP-001",
            "Preserva ownership das ações financeiras.",
            "TRIGGERED" if financial_actions else "NOT_EVALUATED",
            {"scopes": [item.get("ownership_scope") for item in financial_actions]},
            "Nenhum ownership foi dividido ou transferido implicitamente.",
        ),
        _trace(
            "APV1-CONSERVATION-001",
            "Impede gasto superior às decisões anteriores.",
            "NOT_TRIGGERED",
            {
                "financial_actions": total_financial,
                "authorized_financial": authorized_financial,
                "investment_buy": total_investment,
                "suggested_capital": suggested,
                "buy_plus_hold": total_investment + total_hold,
                "investment_budget": investment_budget,
            },
            "Todas as invariantes de conservação foram satisfeitas.",
        ),
        _trace(
            "APV1-DETERMINISM-001",
            "Mantém saída determinística para a cadeia congelada.",
            "TRIGGERED",
            {"generated_at_source": "investment_orchestration.generated_at"},
            "O engine não consultou relógio, banco ou mercado.",
        ),
        _trace(
            "APV1-TRADING-001",
            "Mantém Trading isolado.",
            "NOT_TRIGGERED",
            {"speculative_capital": Decimal("0.00"), "trading_dispatch": False},
            "Nenhuma action criou sinal, ordem ou operação Trading.",
        ),
    ]

    state_fingerprint = _state_fingerprint(state)
    policy_digest = policy.get("decision_fingerprint")
    allocation_digest = allocation.get("decision_fingerprint")
    orchestration_digest = orchestration.get("decision_fingerprint")
    policy_fingerprint = (
        str(policy_digest) if _is_sha256(policy_digest) else None
    )
    allocation_fingerprint = (
        str(allocation_digest) if _is_sha256(allocation_digest) else None
    )
    orchestration_fingerprint = (
        str(orchestration_digest) if _is_sha256(orchestration_digest) else None
    )
    ruleset_fingerprint = _ruleset_fingerprint()
    summary = {
        "authorized_financial_capital": authorized_financial,
        "authorized_investment_capital": investment_budget,
        "financial_actions_total": total_financial,
        "investment_buy_total": total_investment,
        "hold_cash_total": total_hold,
        "action_count": len(actions),
        "primary_action": actions[0]["title"] if actions else None,
    }
    result: dict[str, Any] = {
        "action_plan_id": None,
        "household_id": household_id,
        "financial_state_snapshot_id": state.get("snapshot_id"),
        "financial_policy_decision_id": policy.get("policy_id"),
        "capital_allocation_decision_id": allocation.get("allocation_id"),
        "investment_orchestration_decision_id": orchestration.get("orchestration_id"),
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "status": status,
        "currency": currency,
        "period": period,
        "summary": summary,
        "actions": actions,
        "information_actions": [item for item in actions if item["category"] == "INFORMATION"],
        "financial_actions": financial_actions,
        "investment_actions": investment_actions,
        "hold_actions": hold_actions,
        "total_financial_actions": total_financial,
        "total_investment_actions": total_investment,
        "total_hold_cash": total_hold,
        "speculative_capital": Decimal("0.00"),
        "trading_dispatch": False,
        "blockers": blockers,
        "warnings": warnings,
        "missing_information": missing_information,
        "evidence": evidence,
        "rule_traces": traces,
        "state_fingerprint": state_fingerprint,
        "policy_fingerprint": policy_fingerprint,
        "allocation_fingerprint": allocation_fingerprint,
        "orchestration_fingerprint": orchestration_fingerprint,
        "ruleset_fingerprint": ruleset_fingerprint,
        "decision_fingerprint": "",
        "generated_at": generated_at,
        "created_at": None,
    }
    result["decision_fingerprint"] = decision_fingerprint_from_payload(result)
    return result

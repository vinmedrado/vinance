from __future__ import annotations

import hashlib
import json
import string
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Iterable, Mapping, Sequence

from backend.app.financial_policy.engine import (
    decision_fingerprint_from_payload as financial_policy_fingerprint_from_payload,
)

from backend.app.capital_allocation.rules import (
    BUCKET_BY_PRIORITY,
    ENGINE_VERSION,
    INFORMATIONAL_PRIORITY_CODES,
    INVESTMENT_PRIORITY_CODE,
    MONETARY_PRIORITY_CODES,
    RULE_CATALOG,
    RULES,
    RULES_VERSION,
    SUPPORTED_FINANCIAL_POLICY_VERSION,
    SUPPORTED_FINANCIAL_STATE_VERSION,
    SUPPORTED_INVESTMENT_READINESS,
    SUPPORTED_POLICY_RULES_VERSION,
    SUPPORTED_POLICY_STATES,
)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(RULES.money_quantum, rounding=ROUND_DOWN)


def _as_datetime(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field} must be a valid datetime") from exc
    else:
        raise ValueError(f"{field} is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _sha256_payload(value: Any) -> str:
    canonical = json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _dedupe_messages(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        code = str(item.get("code") or "UNSPECIFIED")
        fields = tuple(str(field) for field in item.get("fields") or [])
        key = (code, fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "code": code,
                "message": str(item.get("message") or code),
                "fields": list(fields),
                "rule_ids": [str(rule_id) for rule_id in item.get("rule_ids") or []],
            }
        )
    return result


def _evidence(code: str, label: str, value: Any, unit: str, source: str) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "value": value,
        "unit": unit,
        "source": source,
    }


def _trace(
    rule_id: str,
    outcome: str,
    *,
    observed_values: Mapping[str, Any],
    rule_parameters: Mapping[str, Any] | None = None,
    explanation: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_version": RULES_VERSION,
        "description": RULE_CATALOG[rule_id],
        "outcome": outcome,
        "observed_values": dict(observed_values),
        "rule_parameters": dict(rule_parameters or {}),
        "explanation": explanation,
    }


def _policy_messages(policy: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return _dedupe_messages(
        item for item in (policy.get(key) or []) if isinstance(item, Mapping)
    )


def _semantic_state(state: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(state))
    result.pop("snapshot_id", None)
    return result


def _ruleset_fingerprint() -> str:
    return _sha256_payload(
        {
            "engine_version": ENGINE_VERSION,
            "rules_version": RULES_VERSION,
            "rules": RULES.public_rules(),
            "rule_catalog": dict(RULE_CATALOG),
            "bucket_by_priority": dict(BUCKET_BY_PRIORITY),
            "informational_priority_codes": sorted(INFORMATIONAL_PRIORITY_CODES),
            "monetary_priority_codes": sorted(MONETARY_PRIORITY_CODES),
            "investment_priority_code": INVESTMENT_PRIORITY_CODE,
        }
    )


def decision_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    """Fingerprint every semantic field while excluding persistence identities."""

    semantic = deepcopy(dict(payload))
    for field in (
        "allocation_id",
        "financial_state_snapshot_id",
        "financial_policy_id",
        "decision_fingerprint",
        "created_at",
    ):
        semantic.pop(field, None)
    source_state = semantic.get("source_financial_state")
    if isinstance(source_state, Mapping):
        semantic["source_financial_state"] = dict(source_state)
        semantic["source_financial_state"].pop("snapshot_id", None)
    source_policy = semantic.get("source_financial_policy")
    if isinstance(source_policy, Mapping):
        semantic["source_financial_policy"] = dict(source_policy)
        semantic["source_financial_policy"].pop("policy_id", None)
    return _sha256_payload(semantic)


def _priority_item(
    priority: Mapping[str, Any],
    *,
    target_type: str,
    target_id: Any = None,
    target_name: str | None = None,
    ownership_scope: str | None = None,
    user_id: Any = None,
    requested_amount: Decimal | None,
    allocated_amount: Decimal,
    status: str,
    reason: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    remaining_need = (
        _money(max(requested_amount - allocated_amount, Decimal("0")))
        if requested_amount is not None
        else None
    )
    return {
        "priority_code": str(priority.get("code")),
        "priority_rank": int(priority.get("rank") or 1),
        "bucket_type": BUCKET_BY_PRIORITY.get(
            str(priority.get("code")), "INFORMATIONAL"
        ),
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
        "ownership_scope": ownership_scope,
        "user_id": user_id,
        "requested_amount": requested_amount,
        "allocated_amount": allocated_amount,
        "remaining_need": remaining_need,
        "status": status,
        "reason": reason,
        "evidence_refs": list(evidence_refs),
    }


def _fund_status(requested: Decimal | None, allocated: Decimal) -> str:
    if requested is None:
        return "NOT_CALCULABLE"
    if requested == 0:
        return "FUNDED"
    if allocated == 0:
        return "UNFUNDED"
    if allocated < requested:
        return "PARTIALLY_FUNDED"
    return "FUNDED"


def _take(
    requested: Decimal,
    *,
    remaining: Decimal,
    ownership_scope: str | None,
    user_id: Any,
    personal_remaining: dict[int, Decimal | None],
    household_remaining: Decimal,
    household_alias_member_id: int | None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Conservatively consume only the matching ownership pool.

    PERSONAL items require a known personal capacity. HOUSEHOLD items consume
    only the residual not attributable to known personal member capacity. This
    prevents an implicit 50/50 split or transfer between ownership scopes.
    """

    requested = _money(max(requested, Decimal("0"))) or Decimal("0.00")
    limit = remaining
    if ownership_scope == "PERSONAL":
        try:
            member_id = int(user_id)
        except (TypeError, ValueError):
            return Decimal("0.00"), remaining, household_remaining
        member_limit = personal_remaining.get(member_id)
        if member_limit is None:
            return Decimal("0.00"), remaining, household_remaining
        limit = min(limit, member_limit)
        if household_alias_member_id == member_id:
            limit = min(limit, household_remaining)
    elif ownership_scope == "HOUSEHOLD":
        limit = min(limit, household_remaining)
    else:
        return Decimal("0.00"), remaining, household_remaining

    allocated = _money(min(requested, limit)) or Decimal("0.00")
    remaining = _money(remaining - allocated) or Decimal("0.00")
    if ownership_scope == "PERSONAL":
        member_id = int(user_id)
        member_limit = personal_remaining[member_id]
        assert member_limit is not None
        personal_remaining[member_id] = _money(member_limit - allocated)
        if household_alias_member_id == member_id:
            household_remaining = _money(household_remaining - allocated) or Decimal(
                "0.00"
            )
    elif ownership_scope == "HOUSEHOLD":
        household_remaining = _money(household_remaining - allocated) or Decimal(
            "0.00"
        )
        if household_alias_member_id is not None:
            member_limit = personal_remaining[household_alias_member_id]
            assert member_limit is not None
            personal_remaining[household_alias_member_id] = _money(
                member_limit - allocated
            )
    return allocated, remaining, household_remaining


def calculate_capital_allocation(
    financial_state: Mapping[str, Any],
    financial_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Allocate proven monthly capital without selecting or executing investments.

    The function is pure and deterministic. It consumes the exact State and
    Policy decisions supplied by the caller, never recomputes either one, never
    reads a database, and has no Trading or Recommendation Engine dependency.
    """

    state = deepcopy(dict(financial_state))
    policy = deepcopy(dict(financial_policy))
    try:
        household_id = int(state["household_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("financial_state.household_id is required") from exc
    generated_at = _as_datetime(
        state.get("evaluated_at"), field="financial_state.evaluated_at"
    )

    metrics = dict(state.get("metrics") or {})
    policy_gate = dict(policy.get("data_gate") or {})
    policy_state = str(policy.get("policy_state") or "")
    readiness = str(policy.get("investment_readiness") or "")
    source_state = dict(policy.get("source_financial_state") or {})
    priorities = [
        dict(item) for item in policy.get("priority_stack") or [] if isinstance(item, Mapping)
    ]
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    missing_information: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    state_version = state.get("engine_version")
    policy_version = policy.get("engine_version")
    policy_rules_version = policy.get("rules_version")
    versions_valid = (
        state_version == SUPPORTED_FINANCIAL_STATE_VERSION
        and policy_version == SUPPORTED_FINANCIAL_POLICY_VERSION
        and policy_rules_version == SUPPORTED_POLICY_RULES_VERSION
    )
    if not versions_valid:
        blockers.append(
            _message(
                "INCOMPATIBLE_SOURCE_VERSION",
                "Financial State ou Financial Policy usa versão incompatível com capital-allocation-v1.",
                fields=("engine_version", "rules_version"),
                rule_ids=("CAV1-DATA-001",),
            )
        )
    traces.append(
        _trace(
            "CAV1-DATA-001",
            "NOT_TRIGGERED" if versions_valid else "TRIGGERED",
            observed_values={
                "state_engine_version": state_version,
                "policy_engine_version": policy_version,
                "policy_rules_version": policy_rules_version,
            },
            rule_parameters={
                "state_engine_version": SUPPORTED_FINANCIAL_STATE_VERSION,
                "policy_engine_version": SUPPORTED_FINANCIAL_POLICY_VERSION,
                "policy_rules_version": SUPPORTED_POLICY_RULES_VERSION,
            },
            explanation="Somente contratos canônicos e versionados podem alimentar esta decisão.",
        )
    )

    policy_household = policy.get("household_id")
    household_matches = str(policy_household) == str(household_id)
    state_snapshot_id = state.get("snapshot_id")
    policy_state_snapshot_id = policy.get("financial_state_snapshot_id")
    source_snapshot_id = source_state.get("snapshot_id")
    snapshot_matches = (
        state_snapshot_id is None
        and policy_state_snapshot_id is None
        and source_snapshot_id is None
    ) or (
        state_snapshot_id is not None
        and policy_state_snapshot_id is not None
        and str(state_snapshot_id) == str(policy_state_snapshot_id)
        and source_snapshot_id is not None
        and str(source_snapshot_id) == str(state_snapshot_id)
    )
    evaluated_matches = False
    if source_state.get("evaluated_at") is not None:
        try:
            evaluated_matches = (
                _as_datetime(
                    source_state.get("evaluated_at"),
                    field="financial_policy.source_financial_state.evaluated_at",
                )
                == generated_at
            )
        except ValueError:
            evaluated_matches = False
    source_version_matches = source_state.get("engine_version") == state_version
    source_quality_matches = source_state.get("data_quality") == state.get(
        "data_quality"
    )
    source_confidence_matches = source_state.get("confidence") == state.get(
        "confidence"
    )
    policy_fingerprint_raw = policy.get("decision_fingerprint")
    policy_fingerprint_valid = (
        isinstance(policy_fingerprint_raw, str)
        and len(policy_fingerprint_raw) == 64
        and all(character in string.hexdigits for character in policy_fingerprint_raw)
        and financial_policy_fingerprint_from_payload(policy)
        == policy_fingerprint_raw
    )
    chain_valid = (
        household_matches
        and snapshot_matches
        and evaluated_matches
        and source_version_matches
        and source_quality_matches
        and source_confidence_matches
        and policy_fingerprint_valid
    )
    if not chain_valid:
        blockers.append(
            _message(
                "SOURCE_CHAIN_MISMATCH",
                "Financial State e Financial Policy não formam a mesma cadeia auditável.",
                fields=(
                    "household_id",
                    "financial_state_snapshot_id",
                    "source_financial_state",
                ),
                rule_ids=("CAV1-DATA-002",),
            )
        )

    ranks = [item.get("rank") for item in priorities]
    priority_codes = [str(item.get("code")) for item in priorities]
    priority_order_valid = bool(priorities) and all(
        isinstance(rank, int) and rank >= 1 for rank in ranks
    ) and len(ranks) == len(set(ranks)) and ranks == sorted(ranks)
    priority_order_valid = priority_order_valid and len(priority_codes) == len(
        set(priority_codes)
    )
    investment_positions = [
        index
        for index, item in enumerate(priorities)
        if item.get("code") == INVESTMENT_PRIORITY_CODE
    ]
    if investment_positions != [len(priorities) - 1]:
        priority_order_valid = False
    if any(
        str(item.get("code"))
        not in INFORMATIONAL_PRIORITY_CODES
        | MONETARY_PRIORITY_CODES
        | {INVESTMENT_PRIORITY_CODE}
        for item in priorities
    ):
        priority_order_valid = False
    if not priority_order_valid:
        blockers.append(
            _message(
                "INVALID_POLICY_PRIORITY_STACK",
                "A ordem de prioridades da Financial Policy é inválida ou não auditável.",
                fields=("financial_policy.priority_stack",),
                rule_ids=("CAV1-ORDER-001",),
            )
        )
    traces.append(
        _trace(
            "CAV1-DATA-002",
            "NOT_TRIGGERED" if chain_valid else "TRIGGERED",
            observed_values={
                "state_household_id": household_id,
                "policy_household_id": policy_household,
                "state_snapshot_id": state_snapshot_id,
                "policy_state_snapshot_id": policy_state_snapshot_id,
                "evaluated_at_matches": evaluated_matches,
                "source_quality_matches": source_quality_matches,
                "source_confidence_matches": source_confidence_matches,
                "policy_fingerprint_valid": policy_fingerprint_valid,
            },
            explanation="State e Policy precisam apontar para a mesma realidade financeira.",
        )
    )
    traces.append(
        _trace(
            "CAV1-ORDER-001",
            "NOT_TRIGGERED" if priority_order_valid else "TRIGGERED",
            observed_values={"priority_codes": priority_codes, "ranks": ranks},
            explanation="O Allocation Engine preserva a ordem formal emitida pela Policy.",
        )
    )

    state_quality = str(state.get("data_quality") or "INSUFFICIENT")
    confidence_raw = state.get("confidence")
    try:
        confidence = int(confidence_raw) if confidence_raw is not None else None
    except (TypeError, ValueError):
        confidence = None
    critical_stale = [str(item) for item in policy_gate.get("critical_stale_fields") or []]
    policy_gate_status = str(policy_gate.get("status") or "BLOCKED")
    policy_supported = policy_state in SUPPORTED_POLICY_STATES
    readiness_supported = readiness in SUPPORTED_INVESTMENT_READINESS
    data_blocked = (
        policy_state == "DATA_BLOCKED"
        or policy_gate_status == "BLOCKED"
        or state_quality in {"INSUFFICIENT", "INCONSISTENT"}
        or bool(critical_stale)
        or not policy_supported
        or not readiness_supported
    )
    if data_blocked:
        blockers.extend(_policy_messages(policy, "blockers"))
        blockers.append(
            _message(
                "FINANCIAL_DATA_GATE_BLOCKED",
                "Os dados ou a política atual não permitem distribuir capital com segurança.",
                fields=tuple(
                    [*critical_stale, *[str(item) for item in state.get("inconsistencies") or []]]
                ),
                rule_ids=("CAV1-DATA-003",),
            )
        )
    if state_quality in {"PARTIAL", "STALE"} or policy_gate_status == "LIMITED":
        warnings.append(
            _message(
                "SOURCE_DATA_LIMITED",
                "A alocação usa somente os valores conhecidos; dados parciais ou stale podem alterar a próxima decisão.",
                fields=tuple(
                    [
                        *[str(item) for item in state.get("missing_fields") or []],
                        *[str(item) for item in state.get("stale_fields") or []],
                    ]
                ),
                rule_ids=("CAV1-DATA-003",),
            )
        )
    warnings.extend(_policy_messages(policy, "warnings"))
    warnings.extend(_policy_messages(policy, "limitations"))
    missing_information.extend(_policy_messages(policy, "missing_information"))
    if state.get("missing_fields"):
        missing_information.append(
            _message(
                "FINANCIAL_STATE_FIELDS_MISSING",
                "Dados ausentes no Financial State podem alterar os valores alocados.",
                fields=tuple(str(item) for item in state.get("missing_fields") or []),
                rule_ids=("CAV1-DATA-003",),
            )
        )
    traces.append(
        _trace(
            "CAV1-DATA-003",
            "TRIGGERED" if data_blocked else "NOT_TRIGGERED",
            observed_values={
                "state_quality": state_quality,
                "state_confidence": confidence,
                "policy_state": policy_state,
                "policy_gate_status": policy_gate_status,
                "critical_stale_fields": critical_stale,
            },
            explanation="Bloqueio preserva None como desconhecido e impede uma distribuição fictícia.",
        )
    )

    currencies = sorted(
        {str(item).upper() for item in policy_gate.get("currencies") or [] if item}
    )
    missing_currency_fields = [
        str(item) for item in policy_gate.get("missing_currency_fields") or []
    ]
    incompatible_currencies = [
        item for item in currencies if item != RULES.settlement_currency
    ]
    currency_blocked = bool(incompatible_currencies or missing_currency_fields)
    if currency_blocked:
        blockers.append(
            _message(
                "CURRENCY_CONVERSION_MISSING",
                "Moedas não comparáveis não foram convertidas sem uma fonte canônica de FX.",
                fields=tuple([*incompatible_currencies, *missing_currency_fields]),
                rule_ids=("CAV1-DATA-004",),
            )
        )
    traces.append(
        _trace(
            "CAV1-DATA-004",
            "TRIGGERED" if currency_blocked else "NOT_TRIGGERED",
            observed_values={
                "currencies": currencies,
                "missing_currency_fields": missing_currency_fields,
            },
            rule_parameters={"settlement_currency": RULES.settlement_currency, "fx_provider": None},
            explanation="capital-allocation-v1 não inventa cotações de câmbio.",
        )
    )

    invalid_ownership_fields: list[str] = []
    owned_policy_records = (
        ("debt_policy.debts", (policy.get("debt_policy") or {}).get("debts") or []),
        ("goal_policy.goals", (policy.get("goal_policy") or {}).get("goals") or []),
    )
    for domain, records in owned_policy_records:
        for index, raw in enumerate(records):
            if not isinstance(raw, Mapping):
                invalid_ownership_fields.append(f"{domain}.{index}")
                continue
            scope = str(raw.get("ownership_scope") or "")
            if scope not in {"PERSONAL", "HOUSEHOLD"}:
                invalid_ownership_fields.append(f"{domain}.{index}.ownership_scope")
            elif scope == "PERSONAL":
                try:
                    int(raw.get("user_id"))
                except (TypeError, ValueError):
                    invalid_ownership_fields.append(f"{domain}.{index}.user_id")
    if invalid_ownership_fields:
        blockers.append(
            _message(
                "INVALID_FINANCIAL_OWNERSHIP",
                "Uma prioridade sem ownership inequívoco não pode receber capital.",
                fields=tuple(invalid_ownership_fields),
                rule_ids=("CAV1-OWN-001",),
            )
        )

    investment_capacity = _decimal(metrics.get("investment_capacity"))
    savings_capacity = _decimal(metrics.get("savings_capacity"))
    disposable_income = _decimal(metrics.get("disposable_income"))
    capital_inconsistent = (
        (investment_capacity is not None and investment_capacity < 0)
        or (
            investment_capacity is not None
            and savings_capacity is not None
            and investment_capacity > savings_capacity
        )
    )
    if capital_inconsistent:
        blockers.append(
            _message(
                "INCONSISTENT_CAPITAL_CAPACITY",
                "A capacidade de investimento contradiz a capacidade financeira do State.",
                fields=("metrics.investment_capacity", "metrics.savings_capacity"),
                rule_ids=("CAV1-CAPITAL-001", "CAV1-CONSERVE-001"),
            )
        )
    if investment_capacity is None:
        blockers.append(
            _message(
                "ALLOCATABLE_CAPITAL_UNKNOWN",
                "A capacidade mensal de investimento é desconhecida; nenhum valor foi inventado.",
                fields=("metrics.investment_capacity",),
                rule_ids=("CAV1-CAPITAL-001",),
            )
        )

    member_names: dict[int, str | None] = {}
    personal_initial: dict[int, Decimal | None] = {}
    for raw in state.get("member_views") or []:
        if not isinstance(raw, Mapping):
            continue
        try:
            member_id = int(raw["user_id"])
        except (KeyError, TypeError, ValueError):
            continue
        member_names[member_id] = raw.get("full_name")
        member_capacity = _decimal((raw.get("metrics") or {}).get("investment_capacity"))
        personal_initial[member_id] = (
            _money(max(member_capacity, Decimal("0")))
            if member_capacity is not None
            else None
        )
    known_personal_total = sum(
        (value for value in personal_initial.values() if value is not None),
        Decimal("0.00"),
    )
    every_personal_pool_known = bool(personal_initial) and all(
        value is not None for value in personal_initial.values()
    )
    ownership_capacity_conflict = (
        investment_capacity is not None
        and investment_capacity >= 0
        and len(personal_initial) > 1
        and known_personal_total > (_money(investment_capacity) or Decimal("0.00"))
    )
    if ownership_capacity_conflict:
        blockers.append(
            _message(
                "UNRECONCILED_CAPITAL_OWNERSHIP",
                (
                    "As capacidades pessoais excedem a capacidade consolidada; não é seguro "
                    "atribuir a redução causada por despesas compartilhadas a um membro."
                ),
                fields=tuple(
                    ["metrics.investment_capacity"]
                    + [
                        f"member_views.{member_id}.metrics.investment_capacity"
                        for member_id in sorted(personal_initial)
                    ]
                ),
                rule_ids=("CAV1-OWN-001",),
            )
        )

    capacity_evidence = [
        item
        for item in policy.get("evidence") or []
        if isinstance(item, Mapping) and item.get("code") == "INVESTMENT_CAPACITY"
    ]
    evidence_capacity_raw = (
        capacity_evidence[0].get("value") if len(capacity_evidence) == 1 else None
    )
    evidence_capacity = _decimal(evidence_capacity_raw)
    policy_capacity_matches = len(capacity_evidence) == 1 and (
        (evidence_capacity_raw is None and investment_capacity is None)
        or (
            evidence_capacity is not None
            and investment_capacity is not None
            and evidence_capacity == investment_capacity
        )
    )
    if not policy_capacity_matches:
        blockers.append(
            _message(
                "POLICY_CAPACITY_MISMATCH",
                "A evidência de capacidade da Policy diverge do Financial State fornecido.",
                fields=("financial_policy.evidence.INVESTMENT_CAPACITY",),
                rule_ids=("CAV1-DATA-002", "CAV1-CAPITAL-001"),
            )
        )
    allocatable = (
        _money(investment_capacity)
        if not blockers
        and investment_capacity is not None
        else None
    )
    traces.append(
        _trace(
            "CAV1-CAPITAL-001",
            "TRIGGERED" if allocatable is not None else "NOT_EVALUATED",
            observed_values={
                "investment_capacity": investment_capacity,
                "savings_capacity": savings_capacity,
                "policy_evidence_capacity": evidence_capacity,
            },
            explanation=(
                "Capital alocável é a capacidade de investimento mensal conhecida no State."
                if allocatable is not None
                else "O capital não foi calculado porque a entrada não passou pelo data gate."
            ),
        )
    )
    traces.append(
        _trace(
            "CAV1-CAPITAL-002",
            "NOT_TRIGGERED",
            observed_values={
                "total_assets": _decimal(metrics.get("total_assets")),
                "allocatable_capital_source": "metrics.investment_capacity",
            },
            explanation="Imóveis, veículos e patrimônio existente permanecem fora do caixa distribuível.",
        )
    )

    allocations: list[dict[str, Any]] = []
    remaining = allocatable or Decimal("0.00")
    personal_remaining = dict(personal_initial)
    household_alias_member_id: int | None = None
    sole_member_capacity = (
        next(iter(personal_initial.values())) if len(personal_initial) == 1 else None
    )
    if (
        every_personal_pool_known
        and len(personal_initial) == 1
        and sole_member_capacity == remaining
    ):
        # A one-member household has no second person across whom capital could
        # be transferred. Both scopes reconcile the exact same bounded pool.
        household_alias_member_id = next(iter(personal_initial))
        household_remaining = remaining
    elif every_personal_pool_known:
        household_remaining = (
            _money(max(remaining - known_personal_total, Decimal("0")))
            or Decimal("0.00")
        )
    else:
        # A positive aggregate residual is not proof that it belongs to the
        # household when one or more personal pools are unknown.
        household_remaining = Decimal("0.00")
        unknown_members = [
            str(member_id)
            for member_id, value in personal_initial.items()
            if value is None
        ]
        missing_information.append(
            _message(
                "CAPITAL_OWNERSHIP_BREAKDOWN_INCOMPLETE",
                "O pool compartilhado não foi inferido porque a capacidade pessoal não está completa.",
                fields=tuple(
                    f"member_views.{member_id}.metrics.investment_capacity"
                    for member_id in unknown_members
                )
                or ("member_views",),
                rule_ids=("CAV1-OWN-001",),
            )
        )

    can_allocate = allocatable is not None and not blockers
    has_unresolved_monetary = False
    investment_priority: dict[str, Any] | None = None

    for priority in priorities:
        code = str(priority.get("code"))
        if code == INVESTMENT_PRIORITY_CODE:
            investment_priority = priority
            continue
        if code in INFORMATIONAL_PRIORITY_CODES:
            allocations.append(
                _priority_item(
                    priority,
                    target_type="DATA",
                    requested_amount=None,
                    allocated_amount=Decimal("0.00"),
                    status="BLOCKED" if code == "COMPLETE_CRITICAL_DATA" else "NOT_CALCULABLE",
                    reason=str(priority.get("explanation") or "Informação necessária antes da alocação."),
                    evidence_refs=priority.get("evidence_refs") or [],
                )
            )
            continue
        if code not in MONETARY_PRIORITY_CODES:
            continue

        if code == "STABILIZE_CASH_FLOW":
            requested = (
                _money(abs(disposable_income))
                if disposable_income is not None and disposable_income < 0
                else (Decimal("0.00") if disposable_income is not None else None)
            )
            allocated = Decimal("0.00")
            if can_allocate and requested is not None:
                allocated, remaining, household_remaining = _take(
                    requested,
                    remaining=remaining,
                    ownership_scope="HOUSEHOLD",
                    user_id=None,
                    personal_remaining=personal_remaining,
                    household_remaining=household_remaining,
                    household_alias_member_id=household_alias_member_id,
                )
            status = _fund_status(requested, allocated) if can_allocate else "BLOCKED"
            allocations.append(
                _priority_item(
                    priority,
                    target_type="CASH_FLOW",
                    target_name="Recuperação do fluxo de caixa",
                    ownership_scope="HOUSEHOLD",
                    requested_amount=requested,
                    allocated_amount=allocated,
                    status=status,
                    reason=(
                        "O déficit mensal conhecido precede qualquer novo investimento."
                        if requested is not None
                        else "O déficit não é calculável com os dados atuais."
                    ),
                    evidence_refs=("DISPOSABLE_INCOME", "INVESTMENT_CAPACITY"),
                )
            )
            has_unresolved_monetary |= status not in {"FUNDED", "ALLOCATED"}
            traces.append(
                _trace(
                    "CAV1-CASH-001",
                    "TRIGGERED",
                    observed_values={"disposable_income": disposable_income, "allocated_amount": allocated},
                    explanation="Recuperação de caixa foi processada antes de todos os demais buckets.",
                )
            )
            continue

        if code == "REDUCE_DEBT_BURDEN":
            debts = [
                dict(item)
                for item in (policy.get("debt_policy") or {}).get("debts") or []
                if isinstance(item, Mapping)
            ]
            if not debts:
                item = _priority_item(
                    priority,
                    target_type="LIABILITY",
                    requested_amount=None,
                    allocated_amount=Decimal("0.00"),
                    status="NOT_CALCULABLE" if can_allocate else "BLOCKED",
                    reason="A Policy prioriza dívidas, mas não contém saldo individual conhecido.",
                    evidence_refs=("TOTAL_LIABILITIES", "DEBT_SERVICE_RATIO"),
                )
                allocations.append(item)
                has_unresolved_monetary = True
            for debt in debts:
                balance = _decimal(debt.get("current_balance"))
                requested = _money(max(balance, Decimal("0"))) if balance is not None else None
                scope = str(debt.get("ownership_scope") or "") or None
                allocated = Decimal("0.00")
                if can_allocate and requested is not None:
                    allocated, remaining, household_remaining = _take(
                        requested,
                        remaining=remaining,
                        ownership_scope=scope,
                        user_id=debt.get("user_id"),
                        personal_remaining=personal_remaining,
                        household_remaining=household_remaining,
                        household_alias_member_id=household_alias_member_id,
                    )
                status = _fund_status(requested, allocated) if can_allocate else "BLOCKED"
                reason = "Redução adicional limitada ao saldo conhecido e ao capital do mesmo ownership."
                if debt.get("annual_interest_rate_pct") is None:
                    reason += " A taxa é desconhecida e não foi inventada."
                allocations.append(
                    _priority_item(
                        priority,
                        target_type="LIABILITY",
                        target_id=debt.get("id"),
                        target_name=debt.get("name"),
                        ownership_scope=scope,
                        user_id=debt.get("user_id"),
                        requested_amount=requested,
                        allocated_amount=allocated,
                        status=status,
                        reason=reason,
                        evidence_refs=("TOTAL_LIABILITIES", "DEBT_SERVICE_RATIO"),
                    )
                )
                has_unresolved_monetary |= status not in {"FUNDED", "ALLOCATED"}
            traces.append(
                _trace(
                    "CAV1-DEBT-001",
                    "TRIGGERED",
                    observed_values={"debt_count": len(debts), "remaining_capital": remaining},
                    explanation="Saldos foram processados na ordem produzida pela Policy sem payoff inventado.",
                )
            )
            continue

        if code == "BUILD_EMERGENCY_RESERVE":
            reserve = dict(policy.get("reserve_policy") or {})
            gap = _decimal(reserve.get("gap_amount"))
            requested = _money(max(gap, Decimal("0"))) if gap is not None else None
            allocated = Decimal("0.00")
            if can_allocate and requested is not None:
                allocated, remaining, household_remaining = _take(
                    requested,
                    remaining=remaining,
                    ownership_scope="HOUSEHOLD",
                    user_id=None,
                    personal_remaining=personal_remaining,
                    household_remaining=household_remaining,
                    household_alias_member_id=household_alias_member_id,
                )
            status = _fund_status(requested, allocated) if can_allocate else "BLOCKED"
            allocations.append(
                _priority_item(
                    priority,
                    target_type="EMERGENCY_RESERVE",
                    target_name="Reserva de emergência",
                    ownership_scope="HOUSEHOLD",
                    requested_amount=requested,
                    allocated_amount=allocated,
                    status=status,
                    reason=(
                        "O valor necessário é o gap emitido pela Financial Policy; nenhuma regra de meses foi duplicada."
                        if requested is not None
                        else "O alvo ou o gap da reserva não é conhecido pela Policy."
                    ),
                    evidence_refs=("EMERGENCY_RESERVE", "RESERVE_TARGET"),
                )
            )
            has_unresolved_monetary |= status not in {"FUNDED", "ALLOCATED"}
            traces.append(
                _trace(
                    "CAV1-RESERVE-001",
                    "TRIGGERED" if requested is not None else "NOT_EVALUATED",
                    observed_values={
                        "reserve_current": reserve.get("current_amount"),
                        "reserve_gap": gap,
                        "allocated_amount": allocated,
                    },
                    explanation="O Allocation Engine consumiu o target já decidido pela Policy.",
                )
            )
            continue

        if code == "FUND_PRIORITY_GOAL":
            goals = [
                dict(item)
                for item in (policy.get("goal_policy") or {}).get("goals") or []
                if isinstance(item, Mapping) and bool(item.get("requires_priority"))
            ]
            if not goals:
                allocations.append(
                    _priority_item(
                        priority,
                        target_type="GOAL",
                        requested_amount=None,
                        allocated_amount=Decimal("0.00"),
                        status="NOT_CALCULABLE" if can_allocate else "BLOCKED",
                        reason="A Policy prioriza objetivos, mas não expõe um objetivo financiável.",
                        evidence_refs=("PRIORITY_GOALS",),
                    )
                )
                has_unresolved_monetary = True
            for goal in goals:
                periodic = _decimal(goal.get("required_monthly_funding"))
                gap = _decimal(goal.get("funding_gap"))
                deadline = goal.get("deadline")
                if periodic is not None:
                    requested = _money(max(periodic, Decimal("0")))
                    temporal_reason = "O aporte mensal requerido veio da Policy e do prazo conhecido."
                elif deadline is None and gap is not None:
                    requested = _money(max(gap, Decimal("0")))
                    temporal_reason = "Sem deadline, nenhum prazo foi inventado; o gap conhecido limita o aporte do período."
                    warnings.append(
                        _message(
                            "GOAL_PERIOD_UNKNOWN",
                            "O objetivo não possui deadline; não existe meta periódica temporal verificável.",
                            fields=(f"goals.{goal.get('id', 'unknown')}.deadline",),
                            rule_ids=("CAV1-GOAL-001",),
                        )
                    )
                else:
                    requested = None
                    temporal_reason = "O valor periódico não é calculável sem gap e prazo suficientes."
                scope = str(goal.get("ownership_scope") or "") or None
                allocated = Decimal("0.00")
                if can_allocate and requested is not None:
                    allocated, remaining, household_remaining = _take(
                        requested,
                        remaining=remaining,
                        ownership_scope=scope,
                        user_id=goal.get("user_id"),
                        personal_remaining=personal_remaining,
                        household_remaining=household_remaining,
                        household_alias_member_id=household_alias_member_id,
                    )
                status = _fund_status(requested, allocated) if can_allocate else "BLOCKED"
                allocations.append(
                    _priority_item(
                        priority,
                        target_type="GOAL",
                        target_id=goal.get("id"),
                        target_name=goal.get("name"),
                        ownership_scope=scope,
                        user_id=goal.get("user_id"),
                        requested_amount=requested,
                        allocated_amount=allocated,
                        status=status,
                        reason=temporal_reason + " O ownership original foi preservado.",
                        evidence_refs=("PRIORITY_GOALS", "INVESTMENT_CAPACITY"),
                    )
                )
                has_unresolved_monetary |= status not in {"FUNDED", "ALLOCATED"}
            traces.append(
                _trace(
                    "CAV1-GOAL-001",
                    "TRIGGERED" if goals else "NOT_EVALUATED",
                    observed_values={"priority_goal_ids": [item.get("id") for item in goals]},
                    explanation="Goals foram financiados na ordem exata da Policy, sem deadline arbitrário.",
                )
            )

    if investment_priority is None:
        has_unresolved_monetary = True

    investment_allowed = (
        can_allocate
        and investment_priority is not None
        and policy_state != "CASHFLOW_RECOVERY"
        and readiness in {"LIMITED", "READY"}
        and not has_unresolved_monetary
    )
    investment_amount = remaining if investment_allowed else Decimal("0.00")
    if investment_allowed:
        remaining = Decimal("0.00")
    investment_status = (
        "ALLOCATED"
        if investment_amount > 0
        else ("FUNDED" if investment_allowed else "BLOCKED")
    )
    if investment_priority is not None:
        allocations.append(
            _priority_item(
                investment_priority,
                target_type="INVESTMENT",
                target_name="Capital elegível para investimentos",
                requested_amount=(investment_amount if investment_allowed else Decimal("0.00")),
                allocated_amount=investment_amount,
                status=investment_status,
                reason=(
                    "O capital residual está elegível para o Autopilot 4; nenhum ativo específico foi selecionado."
                    if investment_allowed
                    else "A Policy, o data gate ou prioridades superiores impedem novo capital para investimento."
                ),
                evidence_refs=("INVESTMENT_READINESS", "INVESTMENT_CAPACITY"),
            )
        )
    traces.append(
        _trace(
            "CAV1-INVEST-001",
            "TRIGGERED" if investment_amount > 0 else "NOT_TRIGGERED",
            observed_values={
                "investment_readiness": readiness,
                "higher_priorities_resolved": not has_unresolved_monetary,
                "investment_bucket_amount": investment_amount,
            },
            explanation="Somente o residual permitido pela Policy foi classificado como investment bucket.",
        )
    )

    speculative_amount = _money(RULES.speculative_capital_amount) or Decimal("0.00")
    traces.append(
        _trace(
            "CAV1-PROTECT-001",
            "NOT_TRIGGERED",
            observed_values={"speculative_capital": speculative_amount, "trading_dispatch": False},
            rule_parameters={"speculative_capital_amount": RULES.speculative_capital_amount},
            explanation="Nenhum capital foi enviado ao Trading V2 e nenhuma operação paper foi criada.",
        )
    )
    traces.append(
        _trace(
            "CAV1-OWN-001",
            (
                "TRIGGERED"
                if invalid_ownership_fields or ownership_capacity_conflict
                else "NOT_TRIGGERED"
            ),
            observed_values={
                "personal_capacity": personal_initial,
                "known_personal_total": known_personal_total,
                "consolidated_capacity": investment_capacity,
                "personal_remaining": personal_remaining,
                "household_remaining_pool": household_remaining,
                "invalid_ownership_fields": invalid_ownership_fields,
                "ownership_capacity_conflict": ownership_capacity_conflict,
            },
            explanation=(
                "Uma prioridade com ownership inválido bloqueou toda a alocação."
                if invalid_ownership_fields
                else (
                    "Capacidades pessoais incompatíveis com o consolidado bloquearam a alocação."
                    if ownership_capacity_conflict
                    else "Nenhuma prioridade pessoal consumiu capacidade de outro membro ou do household."
                )
            ),
        )
    )

    allocated_capital = _money(sum((item["allocated_amount"] for item in allocations), Decimal("0"))) or Decimal("0.00")
    remaining = _money(remaining) or Decimal("0.00")
    if allocatable is not None:
        conservation_valid = (
            all(item["allocated_amount"] >= 0 for item in allocations)
            and allocated_capital <= allocatable
            and remaining >= 0
            and allocated_capital + remaining == allocatable
        )
        if not conservation_valid:
            raise AssertionError("capital allocation conservation invariant violated")
    else:
        conservation_valid = allocated_capital == 0 and remaining == 0
    traces.append(
        _trace(
            "CAV1-CONSERVE-001",
            "NOT_TRIGGERED" if conservation_valid else "TRIGGERED",
            observed_values={
                "allocatable_capital": allocatable,
                "allocated_capital": allocated_capital,
                "remaining_capital": remaining if allocatable is not None else None,
            },
            explanation="O somatório foi reconciliado após cada alocação.",
        )
    )
    traces.append(
        _trace(
            "CAV1-ROUND-001",
            "TRIGGERED",
            observed_values={"quantum": RULES.money_quantum, "rounding_mode": RULES.rounding_mode},
            explanation="Todos os valores monetários foram arredondados deterministicamente para baixo em centavos.",
        )
    )

    protected_total = _money(
        sum(
            (
                item["allocated_amount"]
                for item in allocations
                if item["bucket_type"] == "PROTECTED_CAPITAL"
            ),
            Decimal("0"),
        )
    ) or Decimal("0.00")
    goal_total = _money(
        sum(
            (
                item["allocated_amount"]
                for item in allocations
                if item["bucket_type"] == "GOAL_CAPITAL"
            ),
            Decimal("0"),
        )
    ) or Decimal("0.00")
    bucket_totals = {
        "protected_capital": protected_total,
        "goal_capital": goal_total,
        "investment_capital": investment_amount,
        "speculative_capital": speculative_amount,
    }
    unfunded = [
        deepcopy(item)
        for item in allocations
        if item["target_type"] not in {"DATA", "INVESTMENT"}
        and item["status"] in {"NOT_CALCULABLE", "UNFUNDED", "PARTIALLY_FUNDED", "BLOCKED"}
    ]
    if allocatable is None or blockers:
        allocation_status = "BLOCKED"
    elif (
        allocatable == 0
        or policy_state == "CASHFLOW_RECOVERY"
        or readiness == "BLOCKED"
        or bool(unfunded)
    ):
        allocation_status = "CONSTRAINED"
    elif investment_amount > 0:
        allocation_status = "SURPLUS"
    else:
        allocation_status = "ACTIVE"

    member_impacts: list[dict[str, Any]] = []
    for member_id in sorted(member_names):
        initial = personal_initial.get(member_id)
        member_remaining = personal_remaining.get(member_id)
        allocated_personal = (
            _money(initial - member_remaining)
            if initial is not None and member_remaining is not None
            else Decimal("0.00")
        ) or Decimal("0.00")
        member_impacts.append(
            {
                "user_id": member_id,
                "full_name": member_names[member_id],
                "personal_allocatable_capital": initial,
                "allocated_to_personal_priorities": allocated_personal,
                "remaining_personal_capacity": member_remaining,
                "explanation": (
                    "A visão mostra apenas o impacto de prioridades PERSONAL; nenhuma divisão 50/50 foi presumida."
                    if initial is not None
                    else "A capacidade pessoal é desconhecida e não foi substituída pela capacidade de outro membro."
                ),
            }
        )

    evidence = [
        _evidence("ALLOCATION_PERIOD", "Período da decisão", RULES.allocation_period, "PERIOD", "capital_allocation.rules"),
        _evidence("DISPOSABLE_INCOME", "Renda disponível", disposable_income, "BRL_MONTHLY", "financial_state.metrics.disposable_income"),
        _evidence("SAVINGS_CAPACITY", "Capacidade de poupança", savings_capacity, "BRL_MONTHLY", "financial_state.metrics.savings_capacity"),
        _evidence("INVESTMENT_CAPACITY", "Capital alocável comprovado", allocatable, "BRL_MONTHLY", "financial_state.metrics.investment_capacity"),
        _evidence("TOTAL_ASSETS", "Patrimônio existente não usado como caixa", _decimal(metrics.get("total_assets")), "BRL", "financial_state.metrics.total_assets"),
        _evidence("POLICY_STATE", "Estado da política", policy_state, "STATE", "financial_policy.policy_state"),
        _evidence("INVESTMENT_READINESS", "Prontidão para investir", readiness, "STATE", "financial_policy.investment_readiness"),
        _evidence("ALLOCATED_CAPITAL", "Capital alocado", allocated_capital, "BRL_MONTHLY", "capital_allocation.allocations"),
        _evidence("REMAINING_CAPITAL", "Capital não alocado", remaining if allocatable is not None else None, "BRL_MONTHLY", "capital_allocation.remaining_capital"),
    ]

    input_fingerprint = _sha256_payload(_semantic_state(state))
    policy_fingerprint = (
        str(policy_fingerprint_raw)
        if isinstance(policy_fingerprint_raw, str) and len(policy_fingerprint_raw) == 64
        else _sha256_payload(policy)
    )
    ruleset_fingerprint = _ruleset_fingerprint()
    blockers = _dedupe_messages(blockers)
    warnings = _dedupe_messages(warnings)
    missing_information = _dedupe_messages(missing_information)
    data_gate_status = (
        "BLOCKED"
        if blockers or allocatable is None
        else ("LIMITED" if warnings or state_quality in {"PARTIAL", "STALE"} else "PASS")
    )
    core_decision = {
        "household_id": household_id,
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "allocation_period": RULES.allocation_period,
        "allocation_status": allocation_status,
        "currency": RULES.settlement_currency,
        "allocatable_capital": allocatable,
        "allocated_capital": allocated_capital,
        "remaining_capital": remaining if allocatable is not None else None,
        "investment_bucket_amount": investment_amount,
        "bucket_totals": bucket_totals,
        "allocations": allocations,
        "unfunded_priorities": unfunded,
        "member_impacts": member_impacts,
        "blockers": blockers,
        "warnings": warnings,
        "missing_information": missing_information,
        "evidence": evidence,
        "rules_evaluated": traces,
        "data_gate": {
            "status": data_gate_status,
            "state_quality": state_quality,
            "state_confidence": confidence,
            "policy_state": policy_state or None,
            "investment_readiness": readiness or None,
            "currencies": currencies or [RULES.settlement_currency],
            "critical_stale_fields": critical_stale,
            "consistency_checks": {
                "versions_match": versions_valid,
                "source_chain_matches": chain_valid,
                "priority_order_valid": priority_order_valid,
                "policy_capacity_matches_state": policy_capacity_matches,
                "capital_conservation": conservation_valid,
            },
        },
    }
    result = {
        "allocation_id": None,
        "financial_state_snapshot_id": state_snapshot_id,
        "financial_policy_id": policy.get("policy_id"),
        **core_decision,
        "ruleset": {"version": RULES_VERSION, "rules": RULES.public_rules()},
        "source_financial_state": {
            "engine_version": state_version,
            "evaluated_at": generated_at,
            "snapshot_id": state_snapshot_id,
            "data_quality": state_quality,
            "confidence": confidence,
        },
        "source_financial_policy": {
            "engine_version": policy_version,
            "rules_version": policy_rules_version,
            "policy_id": policy.get("policy_id"),
            "policy_state": policy_state or None,
            "investment_readiness": readiness or None,
            "decision_fingerprint": policy_fingerprint,
        },
        "input_fingerprint": input_fingerprint,
        "policy_fingerprint": policy_fingerprint,
        "ruleset_fingerprint": ruleset_fingerprint,
        "decision_fingerprint": "",
        "generated_at": generated_at,
        "created_at": None,
    }
    result["decision_fingerprint"] = decision_fingerprint_from_payload(result)
    return result

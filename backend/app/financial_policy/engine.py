from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence

from backend.app.financial_policy.rules import (
    CRITICAL_DECISION_FIELDS,
    DEBT_DUE_WEIGHTS,
    ENGINE_VERSION,
    GOAL_PRIORITY_WEIGHTS,
    GOAL_URGENCY_WEIGHTS,
    MISSING_INFORMATION_CODES,
    POLICY_STATE_PRECEDENCE,
    PRIORITY_ORDER,
    READINESS_CORE_FIELDS,
    RULE_CATALOG,
    RULES,
    RULES_VERSION,
    SUPPORTED_AGGREGATE_CURRENCIES,
    SUPPORTED_FINANCIAL_STATE_VERSION,
)


PCT_QUANTUM = Decimal("0.01")
MONEY_QUANTUM = Decimal("0.01")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP) if value is not None else None


def _pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return ((numerator / denominator) * Decimal("100")).quantize(PCT_QUANTUM, rounding=ROUND_HALF_UP)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("financial_state.evaluated_at must be a valid datetime") from exc
    else:
        raise ValueError("financial_state.evaluated_at is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


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


_DECISION_FINGERPRINT_FIELDS = (
    "input_fingerprint",
    "ruleset_fingerprint",
    "policy_state",
    "investment_readiness",
    "summary",
    "priority_stack",
    "data_gate",
    "debt_policy",
    "reserve_policy",
    "goal_policy",
    "blockers",
    "warnings",
    "limitations",
    "missing_information",
    "explanations",
    "evidence",
    "member_policy_views",
    "rules_evaluated",
)


def decision_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    """Rebuild the v1 decision digest from its complete semantic contract."""

    return _sha256_payload(
        {field: deepcopy(payload.get(field)) for field in _DECISION_FINGERPRINT_FIELDS}
    )


def _fingerprint(
    financial_state: Mapping[str, Any],
    normalized_inputs: Mapping[str, Any],
    previous_financial_state: Mapping[str, Any] | None,
) -> str:
    current_semantics = deepcopy(dict(financial_state))
    current_semantics.pop("snapshot_id", None)
    previous_semantics = (
        deepcopy(dict(previous_financial_state))
        if previous_financial_state is not None
        else None
    )
    if previous_semantics is not None:
        previous_semantics.pop("snapshot_id", None)
    return _sha256_payload(
        {
            "financial_state": current_semantics,
            "normalized_inputs": normalized_inputs,
            "previous_financial_state": previous_semantics,
        }
    )


def _ruleset_fingerprint() -> str:
    return _sha256_payload(
        {
            "engine_version": ENGINE_VERSION,
            "rules_version": RULES_VERSION,
            "thresholds": RULES.public_thresholds(),
            "rule_catalog": dict(RULE_CATALOG),
            "priority_order": dict(PRIORITY_ORDER),
            "goal_priority_weights": dict(GOAL_PRIORITY_WEIGHTS),
            "goal_urgency_weights": dict(GOAL_URGENCY_WEIGHTS),
            "debt_due_weights": dict(DEBT_DUE_WEIGHTS),
            "policy_state_precedence": POLICY_STATE_PRECEDENCE,
            "critical_decision_fields": CRITICAL_DECISION_FIELDS,
            "readiness_core_fields": READINESS_CORE_FIELDS,
            "supported_aggregate_currencies": SUPPORTED_AGGREGATE_CURRENCIES,
            "missing_information_codes": sorted(MISSING_INFORMATION_CODES),
        }
    )


def _dedupe_messages(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        code = str(item["code"])
        if code not in seen:
            seen.add(code)
            result.append(item)
    return result


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


def _trace(
    rule_id: str,
    outcome: str,
    *,
    observed_values: Mapping[str, Any],
    thresholds: Mapping[str, Any] | None = None,
    explanation: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_version": RULES_VERSION,
        "description": RULE_CATALOG[rule_id],
        "outcome": outcome,
        "observed_values": dict(observed_values),
        "thresholds": dict(thresholds or {}),
        "explanation": explanation,
    }


def _evidence(code: str, label: str, value: Any, unit: str, source: str) -> dict[str, Any]:
    return {"code": code, "label": label, "value": value, "unit": unit, "source": source}


def _stable_identifier_key(value: Any) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def _active_context_records(
    normalized_inputs: Mapping[str, Any],
    domain: str,
    active_statuses: set[str],
    *,
    household_id: int,
) -> list[dict[str, Any]]:
    """Return only records owned by the same effective household as State v1.

    Financial State filters PERSONAL records to active members and HOUSEHOLD
    records to any known member (the recorder may later become inactive). Policy
    explanations must apply the identical boundary instead of reintroducing rows
    excluded from the canonical metrics.
    """

    known_member_ids: set[int] = set()
    active_member_ids: set[int] = set()
    for raw_member in normalized_inputs.get("members") or []:
        try:
            member_user_id = int(raw_member["user_id"])
        except (KeyError, TypeError, ValueError):
            continue
        known_member_ids.add(member_user_id)
        if str(raw_member.get("status", "ACTIVE")).upper() == "ACTIVE":
            active_member_ids.add(member_user_id)

    records: list[dict[str, Any]] = []
    for raw in normalized_inputs.get(domain) or []:
        record = dict(raw)
        try:
            record_household_id = int(record.get("household_id"))
            record_user_id = int(record.get("user_id"))
        except (TypeError, ValueError):
            continue
        scope = str(record.get("ownership_scope", "")).upper()
        if record_household_id != household_id:
            continue
        if scope == "PERSONAL" and record_user_id not in active_member_ids:
            continue
        if scope == "HOUSEHOLD" and record_user_id not in known_member_ids:
            continue
        if scope not in {"PERSONAL", "HOUSEHOLD"}:
            continue
        if str(record.get("status", "ACTIVE")).upper() not in active_statuses:
            continue
        records.append(record)
    return records


def _currency_gate(
    normalized_inputs: Mapping[str, Any], *, household_id: int
) -> tuple[list[str], list[str], list[str]]:
    currencies: set[str] = set(SUPPORTED_AGGREGATE_CURRENCIES)
    unsupported_fields: list[str] = []
    missing_fields: list[str] = []
    domains = (
        ("liabilities", {"ACTIVE", "DEFAULTED"}),
        ("assets", {"ACTIVE"}),
        ("goals", {"ACTIVE"}),
    )
    for domain, statuses in domains:
        for record in _active_context_records(
            normalized_inputs, domain, statuses, household_id=household_id
        ):
            currency_raw = record.get("currency")
            field = f"{domain}.{record.get('id', 'unknown')}.currency"
            if currency_raw is None or not str(currency_raw).strip():
                missing_fields.append(field)
                continue
            currency = str(currency_raw).upper()
            currencies.add(currency)
            if currency not in SUPPORTED_AGGREGATE_CURRENCIES:
                unsupported_fields.append(field)
    return sorted(currencies), unsupported_fields, missing_fields


def _debt_policy(
    metrics: Mapping[str, Any],
    normalized_inputs: Mapping[str, Any],
    *,
    household_id: int,
    evaluated_at: datetime,
    traces: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    limitations: list[dict[str, Any]],
) -> dict[str, Any]:
    total_liabilities = _decimal(metrics.get("total_liabilities"))
    recurring_income = _decimal(metrics.get("recurring_monthly_income"))
    debt_service_ratio = _decimal(metrics.get("debt_service_ratio"))
    debt_to_income = _decimal(metrics.get("debt_to_income"))
    net_worth = _decimal(metrics.get("net_worth"))
    debts = _active_context_records(
        normalized_inputs,
        "liabilities",
        {"ACTIVE", "DEFAULTED"},
        household_id=household_id,
    )
    relevant_debts: list[dict[str, Any]] = []
    unknown_rate_ids: list[Any] = []
    defaulted_ids: list[Any] = []
    high_rate_ids: list[Any] = []
    unknown_due_date_ids: list[Any] = []
    zero_balance_payment_ids: list[Any] = []
    due_priority_ids: list[Any] = []
    due_soon_ids: list[Any] = []
    passed_date_active_ids: list[Any] = []

    for debt in debts:
        balance = _decimal(debt.get("current_balance"))
        payment = _decimal(debt.get("monthly_payment"))
        payment_share = _pct(payment, recurring_income)
        status = str(debt.get("status", "ACTIVE")).upper()
        if (
            status != "DEFAULTED"
            and balance is not None
            and balance <= 0
            and (payment is None or payment <= 0)
        ):
            continue
        if status == "ACTIVE" and balance == 0 and payment is not None and payment > 0:
            zero_balance_payment_ids.append(debt.get("id"))
        rate = _decimal(debt.get("annual_interest_rate_pct"))
        debt_id = debt.get("id")
        due_date = _as_date(debt.get("due_date"))
        days_remaining = (due_date - evaluated_at.date()).days if due_date else None
        if days_remaining is None:
            due_assessment = "UNKNOWN_DUE_DATE"
        elif days_remaining < 0 and status == "ACTIVE":
            due_assessment = "DATE_PASSED_STATUS_ACTIVE"
            passed_date_active_ids.append(debt_id)
            if balance is None or balance > 0:
                due_priority_ids.append(debt_id)
        elif days_remaining <= RULES.near_term_debt_days:
            due_assessment = "DUE_SOON"
            if balance is None or balance > 0:
                due_priority_ids.append(debt_id)
                due_soon_ids.append(debt_id)
        else:
            due_assessment = "SCHEDULED"
        assessment = "STANDARD_KNOWN_COST"
        severity = 0
        if status == "DEFAULTED":
            assessment = "DEFAULTED"
            severity = 3
            defaulted_ids.append(debt_id)
        elif rate is None:
            assessment = "UNKNOWN_COST"
            severity = 1
            unknown_rate_ids.append(debt_id)
        elif rate >= RULES.known_high_cost_debt_apr_pct:
            assessment = "HIGH_COST"
            severity = 2
            high_rate_ids.append(debt_id)
        if debt.get("due_date") is None:
            unknown_due_date_ids.append(debt_id)
        relevant_debts.append(
            {
                "id": debt_id,
                "name": debt.get("name"),
                "ownership_scope": debt.get("ownership_scope"),
                "user_id": debt.get("user_id"),
                "status": debt.get("status"),
                "current_balance": balance,
                "monthly_payment": payment,
                "monthly_payment_share_pct": payment_share,
                "annual_interest_rate_pct": rate,
                "due_date": due_date,
                "days_remaining": days_remaining,
                "due_assessment": due_assessment,
                "assessment": assessment,
                "_severity": severity,
                "_due_severity": (
                    DEBT_DUE_WEIGHTS["DATE_PASSED_STATUS_ACTIVE"]
                    if due_assessment == "DATE_PASSED_STATUS_ACTIVE"
                    else DEBT_DUE_WEIGHTS["DUE_SOON"]
                    if due_assessment == "DUE_SOON"
                    else DEBT_DUE_WEIGHTS["OTHER"]
                ),
                "_payment_pressure": payment if payment is not None else Decimal("-1"),
            }
        )

    relevant_debts.sort(
        key=lambda item: (
            -int(item["_severity"]),
            -int(item["_due_severity"]),
            -Decimal(item["_payment_pressure"]),
            -(
                item_rate
                if (item_rate := _decimal(item.get("annual_interest_rate_pct")))
                is not None
                else Decimal("-1")
            ),
            _stable_identifier_key(item.get("id")),
        )
    )
    for item in relevant_debts:
        item.pop("_severity", None)
        item.pop("_due_severity", None)
        item.pop("_payment_pressure", None)

    if unknown_rate_ids:
        warnings.append(
            _message(
                "DEBT_RATE_UNKNOWN",
                "Há dívida ativa sem taxa informada; ela não foi classificada como cara nem barata.",
                fields=tuple(f"liabilities.{item}.annual_interest_rate_pct" for item in unknown_rate_ids),
                rule_ids=("FPV1-DEBT-002",),
            )
        )
    if unknown_due_date_ids:
        limitations.append(
            _message(
                "DEBT_DUE_DATE_UNKNOWN",
                "Há dívida ativa sem vencimento informado; nenhuma data foi presumida.",
                fields=tuple(
                    f"liabilities.{item}.due_date" for item in unknown_due_date_ids
                ),
            )
        )
    if zero_balance_payment_ids:
        warnings.append(
            _message(
                "DEBT_ZERO_BALANCE_WITH_PAYMENT",
                "Há dívida ativa com saldo zero e parcela positiva; confirme os dados antes de ampliar aportes.",
                fields=tuple(
                    f"liabilities.{item}" for item in zero_balance_payment_ids
                ),
                rule_ids=("FPV1-DEBT-003",),
            )
        )
    if passed_date_active_ids:
        warnings.append(
            _message(
                "DEBT_DATE_PASSED_STATUS_ACTIVE",
                "Há dívida ativa com data informada já passada; ela recebeu prioridade, mas default não foi presumido.",
                fields=tuple(
                    f"liabilities.{item}.due_date" for item in passed_date_active_ids
                ),
                rule_ids=("FPV1-DEBT-005",),
            )
        )
    if due_soon_ids:
        warnings.append(
            _message(
                "DEBT_DUE_SOON",
                "Há obrigação com vencimento conhecido no horizonte próximo da política.",
                fields=tuple(f"liabilities.{item}.due_date" for item in due_soon_ids),
                rule_ids=("FPV1-DEBT-005",),
            )
        )

    traces.append(
        _trace(
            "FPV1-DEBT-001",
            "TRIGGERED" if defaulted_ids else "NOT_TRIGGERED",
            observed_values={"defaulted_debt_ids": defaulted_ids},
            explanation="Default foi considerado somente quando o status explícito é DEFAULTED.",
        )
    )
    traces.append(
        _trace(
            "FPV1-DEBT-002",
            "TRIGGERED"
            if high_rate_ids
            else ("NOT_EVALUATED" if unknown_rate_ids else "NOT_TRIGGERED"),
            observed_values={"high_rate_debt_ids": high_rate_ids, "unknown_rate_debt_ids": unknown_rate_ids},
            thresholds={"known_high_cost_debt_apr_pct": RULES.known_high_cost_debt_apr_pct},
            explanation="Somente taxas conhecidas foram comparadas com o threshold versionado.",
        )
    )
    service_priority = debt_service_ratio is not None and debt_service_ratio >= RULES.debt_service_priority_pct
    service_block = debt_service_ratio is not None and debt_service_ratio >= RULES.debt_service_block_pct
    traces.append(
        _trace(
            "FPV1-DEBT-003",
            "TRIGGERED"
            if service_priority
            else ("NOT_EVALUATED" if debt_service_ratio is None else "NOT_TRIGGERED"),
            observed_values={"debt_service_ratio": debt_service_ratio},
            thresholds={
                "priority_pct": RULES.debt_service_priority_pct,
                "block_pct": RULES.debt_service_block_pct,
            },
            explanation="A parcela mensal foi comparada à renda recorrente usando a métrica do Financial State.",
        )
    )
    dti_warning = debt_to_income is not None and debt_to_income >= RULES.debt_to_income_warning_pct
    traces.append(
        _trace(
            "FPV1-DEBT-004",
            "TRIGGERED"
            if dti_warning
            else ("NOT_EVALUATED" if debt_to_income is None else "NOT_TRIGGERED"),
            observed_values={"debt_to_income": debt_to_income},
            thresholds={"warning_pct": RULES.debt_to_income_warning_pct},
            explanation="DTI isolado gera alerta porque dívidas longas podem distorcer esse indicador.",
        )
    )
    if dti_warning:
        warnings.append(
            _message(
                "DEBT_TO_INCOME_ELEVATED",
                "A relação entre saldo das dívidas e renda anual merece acompanhamento.",
                fields=("metrics.debt_to_income",),
                rule_ids=("FPV1-DEBT-004",),
            )
        )
    traces.append(
        _trace(
            "FPV1-DEBT-005",
            "TRIGGERED" if due_priority_ids else (
                "NOT_EVALUATED" if unknown_due_date_ids else "NOT_TRIGGERED"
            ),
            observed_values={
                "due_priority_debt_ids": due_priority_ids,
                "due_soon_debt_ids": due_soon_ids,
                "passed_date_active_debt_ids": passed_date_active_ids,
                "unknown_due_date_debt_ids": unknown_due_date_ids,
            },
            thresholds={"near_term_debt_days": RULES.near_term_debt_days},
            explanation="Datas conhecidas ordenaram urgência; data passada com status ACTIVE não foi convertida em DEFAULTED.",
        )
    )

    net_worth_negative = net_worth is not None and net_worth < 0
    traces.append(
        _trace(
            "FPV1-NET-001",
            "TRIGGERED" if net_worth_negative else (
                "NOT_EVALUATED" if net_worth is None else "NOT_TRIGGERED"
            ),
            observed_values={"net_worth": net_worth},
            thresholds={"negative_below": Decimal("0.00")},
            explanation="Patrimônio líquido negativo foi considerado sem substituir ativos ou passivos ausentes por zero.",
        )
    )
    if net_worth_negative:
        warnings.append(
            _message(
                "NEGATIVE_NET_WORTH",
                "O patrimônio líquido conhecido é negativo; reduzir passivos deve preceder aportes plenos.",
                fields=("metrics.net_worth",),
                rule_ids=("FPV1-NET-001",),
            )
        )

    return {
        "total_liabilities": total_liabilities,
        "debt_service_ratio": debt_service_ratio,
        "debt_to_income": debt_to_income,
        "net_worth": net_worth,
        "priority_required": bool(
            defaulted_ids
            or high_rate_ids
            or service_priority
            or due_priority_ids
            or net_worth_negative
        ),
        "investment_blocking": bool(defaulted_ids or high_rate_ids or service_block),
        "unknown_rate_debt_ids": unknown_rate_ids,
        "zero_balance_payment_debt_ids": zero_balance_payment_ids,
        "due_priority_debt_ids": due_priority_ids,
        "due_soon_debt_ids": due_soon_ids,
        "debts": relevant_debts,
    }


def _reserve_policy(
    metrics: Mapping[str, Any],
    *,
    traces: list[dict[str, Any]],
    limitations: list[dict[str, Any]],
) -> dict[str, Any]:
    total_expenses = _decimal(metrics.get("total_expenses"))
    fixed_expenses = _decimal(metrics.get("fixed_expenses"))
    total_income = _decimal(metrics.get("total_income"))
    non_recurring_income = _decimal(metrics.get("non_recurring_income"))
    debt_service_ratio = _decimal(metrics.get("debt_service_ratio"))
    reserve = _decimal(metrics.get("emergency_reserve"))
    reserve_months = _decimal(metrics.get("emergency_reserve_months"))

    target_months = RULES.reserve_base_months
    modifiers: list[dict[str, Any]] = []
    target_missing_context: list[str] = []
    fixed_share = _pct(fixed_expenses, total_expenses)
    if fixed_share is not None and fixed_share >= RULES.fixed_expense_pressure_pct:
        target_months += RULES.reserve_modifier_months
        modifiers.append({"code": "FIXED_EXPENSE_PRESSURE", "months": RULES.reserve_modifier_months, "observed_pct": fixed_share})
    elif fixed_share is None:
        target_missing_context.append("fixed_expense_share")
        limitations.append(
            _message(
                "FIXED_EXPENSE_SHARE_UNKNOWN",
                "A composição fixa das despesas não está completa; esse ajuste de reserva não foi aplicado.",
                fields=("metrics.fixed_expenses", "metrics.total_expenses"),
            )
        )

    if debt_service_ratio is not None and debt_service_ratio >= RULES.debt_service_priority_pct:
        target_months += RULES.reserve_modifier_months
        modifiers.append({"code": "DEBT_SERVICE_PRESSURE", "months": RULES.reserve_modifier_months, "observed_pct": debt_service_ratio})
    elif debt_service_ratio is None:
        target_missing_context.append("debt_service_ratio")
        limitations.append(
            _message(
                "DEBT_SERVICE_CONTEXT_UNKNOWN",
                "O comprometimento mensal com dívidas é desconhecido; esse ajuste de reserva não foi aplicado.",
                fields=("metrics.debt_service_ratio",),
            )
        )

    non_recurring_share = _pct(non_recurring_income, total_income)
    if non_recurring_share is not None and non_recurring_share >= RULES.non_recurring_income_dependency_pct:
        target_months += RULES.reserve_modifier_months
        modifiers.append({"code": "NON_RECURRING_INCOME_DEPENDENCY", "months": RULES.reserve_modifier_months, "observed_pct": non_recurring_share})
    elif non_recurring_share is None:
        target_missing_context.append("non_recurring_income_share")
        limitations.append(
            _message(
                "INCOME_STABILITY_PARTIAL",
                "A estabilidade da renda não pôde ser inferida além da classificação recorrente informada.",
                fields=("metrics.non_recurring_income", "metrics.total_income"),
            )
        )

    target_months = min(target_months, RULES.reserve_max_months)
    target_amount = _money(total_expenses * target_months) if total_expenses is not None else None
    gap_amount = _money(max(target_amount - reserve, Decimal("0"))) if target_amount is not None and reserve is not None else None
    if reserve is None or reserve_months is None:
        status = "UNKNOWN"
    elif reserve == 0 and total_expenses is not None and total_expenses > 0:
        status = "ABSENT"
    elif reserve_months < target_months:
        status = "BUILDING"
    elif target_missing_context:
        status = "ADEQUATE_FOR_KNOWN_CONTEXT"
    else:
        status = "ADEQUATE"

    if total_expenses == 0 and reserve_months is None:
        limitations.append(
            _message(
                "RESERVE_WITH_ZERO_EXPENSES_NOT_ASSESSABLE",
                "Com despesas explicitamente iguais a zero, meses de reserva não são matematicamente avaliáveis.",
                fields=("metrics.total_expenses", "metrics.emergency_reserve_months"),
            )
        )
    limitations.extend(
        [
            _message(
                "EMPLOYMENT_STABILITY_NOT_MODELED",
                "Estabilidade profissional ainda não faz parte do modelo e não foi presumida.",
            ),
            _message(
                "DEPENDENTS_NOT_MODELED",
                "Dependentes e responsabilidades familiares ainda não fazem parte do modelo e não foram presumidos.",
            ),
        ]
    )
    traces.append(
        _trace(
            "FPV1-RESERVE-001",
            "TRIGGERED",
            observed_values={
                "fixed_expense_share_pct": fixed_share,
                "debt_service_ratio": debt_service_ratio,
                "non_recurring_income_share_pct": non_recurring_share,
                "applied_modifiers": modifiers,
                "target_months": target_months,
                "missing_context": target_missing_context,
            },
            thresholds={
                "base_months": RULES.reserve_base_months,
                "max_months": RULES.reserve_max_months,
                "modifier_months": RULES.reserve_modifier_months,
                "fixed_expense_pressure_pct": RULES.fixed_expense_pressure_pct,
                "debt_service_pressure_pct": RULES.debt_service_priority_pct,
                "non_recurring_dependency_pct": RULES.non_recurring_income_dependency_pct,
            },
            explanation="O piso prudencial não é um alvo universal: ele foi ajustado somente pelo contexto v1 calculável e as dimensões ainda não modeladas permaneceram explícitas.",
        )
    )
    traces.append(
        _trace(
            "FPV1-RESERVE-002",
            "NOT_EVALUATED"
            if status == "UNKNOWN"
            else (
                "TRIGGERED"
                if status in {"ABSENT", "BUILDING"}
                else "NOT_TRIGGERED"
            ),
            observed_values={"reserve": reserve, "reserve_months": reserve_months, "target_months": target_months},
            thresholds={"target_months": target_months},
            explanation="A reserva foi comparada ao alvo dinâmico sem substituir ausência por zero.",
        )
    )
    return {
        "status": status,
        "current_amount": reserve,
        "current_months": reserve_months,
        "target_months": target_months,
        "target_amount": target_amount,
        "gap_amount": gap_amount,
        "modifiers": modifiers,
        "target_method": "PRUDENTIAL_FLOOR_PLUS_KNOWN_CONTEXT",
        "universal_target_applied": False,
        "unmodeled_context": ["employment_stability", "dependents_and_responsibilities"],
        "target_completeness": (
            "PARTIAL" if target_missing_context else "COMPLETE"
        ),
        "target_missing_context": target_missing_context,
    }


def _goal_policy(
    financial_state: Mapping[str, Any],
    evaluated_at: datetime,
    *,
    goals_declared: bool,
    traces: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    limitations: list[dict[str, Any]],
) -> dict[str, Any]:
    assessed: list[dict[str, Any]] = []
    unknown_gap_ids: list[Any] = []
    unknown_deadline_ids: list[Any] = []
    unknown_deadline_unfunded_ids: list[Any] = []
    priority_goal_ids: list[Any] = []
    capacity_exceeded_ids: list[Any] = []
    unknown_funding_plan_ids: list[Any] = []
    available_monthly_capacity = _decimal(
        dict(financial_state.get("metrics") or {}).get("investment_capacity")
    )
    for raw in financial_state.get("goals") or []:
        if str(raw.get("status", "ACTIVE")) != "ACTIVE":
            continue
        goal = dict(raw)
        goal_id = goal.get("id")
        gap = _decimal(goal.get("funding_gap"))
        deadline = _as_date(goal.get("deadline"))
        days_remaining = (deadline - evaluated_at.date()).days if deadline else None
        explicit_priority = str(goal.get("priority", "LOW"))
        if gap is None:
            unknown_gap_ids.append(goal_id)
        if deadline is None:
            unknown_deadline_ids.append(goal_id)
            if gap is not None and gap > 0:
                unknown_deadline_unfunded_ids.append(goal_id)
        is_urgent = gap is not None and gap > 0 and days_remaining is not None and days_remaining <= RULES.urgent_goal_days
        is_near_high = (
            gap is not None
            and gap > 0
            and explicit_priority in {"HIGH", "MEDIUM"}
            and days_remaining is not None
            and days_remaining <= RULES.near_term_goal_days
        )
        explicitly_high = gap is not None and gap > 0 and explicit_priority == "HIGH"
        requires_priority = bool(is_urgent or is_near_high or explicitly_high)
        if requires_priority:
            priority_goal_ids.append(goal_id)
        required_monthly_funding: Decimal | None = None
        funding_feasibility = "NOT_APPLICABLE"
        if gap is None:
            funding_feasibility = "UNKNOWN_GAP"
            unknown_funding_plan_ids.append(goal_id)
        elif gap <= 0:
            required_monthly_funding = Decimal("0.00")
            funding_feasibility = "FUNDED"
        elif days_remaining is None:
            funding_feasibility = "UNKNOWN_DEADLINE"
            unknown_funding_plan_ids.append(goal_id)
        elif available_monthly_capacity is None:
            funding_feasibility = "UNKNOWN_CAPACITY"
            unknown_funding_plan_ids.append(goal_id)
        else:
            planning_months = max(
                Decimal("1"),
                (Decimal(max(days_remaining, 0)) / Decimal(RULES.goal_planning_month_days))
                .to_integral_value(rounding=ROUND_CEILING),
            )
            required_monthly_funding = _money(gap / planning_months)
            if required_monthly_funding > available_monthly_capacity:
                funding_feasibility = "EXCEEDS_CAPACITY"
                capacity_exceeded_ids.append(goal_id)
            else:
                funding_feasibility = "WITHIN_CAPACITY"
        urgency_score = (
            GOAL_URGENCY_WEIGHTS["OVERDUE"]
            if days_remaining is not None and days_remaining <= 0
            else GOAL_URGENCY_WEIGHTS["URGENT"]
            if is_urgent
            else GOAL_URGENCY_WEIGHTS["NEAR_TERM"]
            if is_near_high
            else GOAL_URGENCY_WEIGHTS["UNSCHEDULED"]
        )
        assessed.append(
            {
                "id": goal_id,
                "name": goal.get("name"),
                "ownership_scope": goal.get("ownership_scope"),
                "user_id": goal.get("user_id"),
                "priority": explicit_priority,
                "target_amount": _decimal(goal.get("target_amount")),
                "current_amount": _decimal(goal.get("current_amount")),
                "funding_gap": gap,
                "deadline": deadline,
                "days_remaining": days_remaining,
                "required_monthly_funding": required_monthly_funding,
                "available_monthly_capacity": available_monthly_capacity,
                "funding_feasibility": funding_feasibility,
                "requires_priority": requires_priority,
                "_sort": (
                    1 if requires_priority else 0,
                    urgency_score,
                    GOAL_PRIORITY_WEIGHTS.get(explicit_priority, 0),
                ),
            }
        )
    assessed.sort(
        key=lambda item: tuple(-part for part in item["_sort"])
        + (_stable_identifier_key(item.get("id")),)
    )
    for item in assessed:
        item.pop("_sort", None)

    if unknown_gap_ids:
        warnings.append(
            _message(
                "GOAL_FUNDING_GAP_UNKNOWN",
                "Há objetivo cujo progresso financeiro não pode ser avaliado.",
                fields=tuple(f"goals.{item}.funding_gap" for item in unknown_gap_ids),
                rule_ids=("FPV1-GOAL-001",),
            )
        )
    if unknown_deadline_ids:
        limitations.append(
            _message(
                "GOAL_DEADLINE_UNKNOWN",
                "Há objetivo sem prazo; nenhum deadline arbitrário foi criado.",
                fields=tuple(f"goals.{item}.deadline" for item in unknown_deadline_ids),
                rule_ids=("FPV1-GOAL-001",),
            )
        )
    if capacity_exceeded_ids:
        warnings.append(
            _message(
                "GOAL_FUNDING_EXCEEDS_CAPACITY",
                "O aporte mensal requerido por um objetivo excede a capacidade financeira conhecida.",
                fields=tuple(f"goals.{item}.funding_gap" for item in capacity_exceeded_ids),
                rule_ids=("FPV1-GOAL-002",),
            )
        )
    traces.append(
        _trace(
            "FPV1-GOAL-001",
            "TRIGGERED"
            if priority_goal_ids
            else (
                "NOT_EVALUATED"
                if unknown_gap_ids or not goals_declared
                else "NOT_TRIGGERED"
            ),
            observed_values={
                "priority_goal_ids": priority_goal_ids,
                "unknown_gap_goal_ids": unknown_gap_ids,
                "unknown_deadline_goal_ids": unknown_deadline_ids,
            },
            thresholds={"urgent_days": RULES.urgent_goal_days, "near_term_days": RULES.near_term_goal_days},
            explanation="Prazos ausentes permaneceram desconhecidos; prioridade HIGH explícita continua válida sem prazo inventado.",
        )
    )
    traces.append(
        _trace(
            "FPV1-GOAL-002",
            "TRIGGERED"
            if capacity_exceeded_ids
            else (
                "NOT_EVALUATED"
                if unknown_funding_plan_ids or not goals_declared
                else "NOT_TRIGGERED"
            ),
            observed_values={
                "available_monthly_capacity": available_monthly_capacity,
                "capacity_exceeded_goal_ids": capacity_exceeded_ids,
                "unknown_funding_plan_goal_ids": unknown_funding_plan_ids,
            },
            thresholds={"planning_month_days": RULES.goal_planning_month_days},
            explanation="O aporte mensal só foi calculado quando gap, prazo e capacidade estavam conhecidos.",
        )
    )
    return {
        "priority_required": bool(priority_goal_ids),
        "priority_goal_ids": priority_goal_ids,
        "unknown_gap_goal_ids": unknown_gap_ids,
        "unknown_deadline_goal_ids": unknown_deadline_ids,
        "unknown_deadline_unfunded_goal_ids": unknown_deadline_unfunded_ids,
        "capacity_exceeded_goal_ids": capacity_exceeded_ids,
        "unknown_funding_plan_goal_ids": unknown_funding_plan_ids,
        "available_monthly_capacity": available_monthly_capacity,
        "goals": assessed,
    }


def _priority(
    code: str,
    title: str,
    explanation: str,
    status: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "explanation": explanation,
        "status": status,
        "evidence_refs": list(evidence_refs),
    }


def _cashflow_deterioration(
    current_metrics: Mapping[str, Any], previous_metrics: Mapping[str, Any]
) -> list[str]:
    transitions = (
        ("disposable_income", False),
        ("savings_capacity", False),
        ("cash_flow", True),
    )
    signals: list[str] = []
    for field, current_must_be_negative in transitions:
        previous_value = _decimal(previous_metrics.get(field))
        current_value = _decimal(current_metrics.get(field))
        if previous_value is None or current_value is None or previous_value <= 0:
            continue
        crossed_boundary = (
            current_value < 0 if current_must_be_negative else current_value <= 0
        )
        if crossed_boundary:
            signals.append(field)
    return signals


def _policy_explanations(
    *,
    policy_state: str,
    readiness: str,
    summary: str,
    priorities: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    debt_policy: Mapping[str, Any],
    reserve_policy: Mapping[str, Any],
    goal_policy: Mapping[str, Any],
    blockers: Sequence[Mapping[str, Any]],
    readiness_limiters: Sequence[str],
    traces: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    active = next(
        (item for item in priorities if item.get("status") == "ACTIVE"),
        priorities[0] if priorities else None,
    )
    decision = str(active.get("title")) if active else summary
    evidence_refs = list(active.get("evidence_refs") or []) if active else []
    rule_prefixes_by_state = {
        "DATA_BLOCKED": ("FPV1-DATA-",),
        "CASHFLOW_RECOVERY": ("FPV1-CASH-",),
        "DEBT_PRIORITY": ("FPV1-DEBT-", "FPV1-NET-"),
        "EMERGENCY_RESERVE_PRIORITY": ("FPV1-RESERVE-",),
        "GOAL_PRIORITY": ("FPV1-GOAL-",),
        "BALANCED_BUILD": ("FPV1-READY-",),
        "INVESTMENT_READY": ("FPV1-READY-",),
    }
    relevant_prefixes = rule_prefixes_by_state[policy_state]
    triggered_rule_ids = [
        str(trace["rule_id"])
        for trace in traces
        if trace.get("outcome") == "TRIGGERED"
        and str(trace.get("rule_id", "")).startswith(relevant_prefixes)
    ]
    if policy_state == "DATA_BLOCKED":
        reason = "A decisão foi limitada pelos bloqueios de dados: " + ", ".join(
            str(item.get("code")) for item in blockers
        )
    elif policy_state == "CASHFLOW_RECOVERY":
        reason = (
            "Fluxo de caixa conhecido: "
            f"{metrics.get('cash_flow')}; renda disponível: {metrics.get('disposable_income')}; "
            f"capacidade de poupança: {metrics.get('savings_capacity')}."
        )
    elif policy_state == "DEBT_PRIORITY":
        reason = (
            f"Passivos conhecidos: {debt_policy.get('total_liabilities')}; "
            f"debt service ratio: {debt_policy.get('debt_service_ratio')}; "
            f"dívidas priorizadas: {debt_policy.get('due_priority_debt_ids') or []}."
        )
    elif policy_state == "EMERGENCY_RESERVE_PRIORITY":
        reason = (
            f"Reserva atual: {reserve_policy.get('current_amount')}; cobertura atual: "
            f"{reserve_policy.get('current_months')} mês(es); alvo vigente: "
            f"{reserve_policy.get('target_months')} mês(es)."
        )
    elif policy_state == "GOAL_PRIORITY":
        priority_ids = set(goal_policy.get("priority_goal_ids") or [])
        goal = next(
            (item for item in goal_policy.get("goals") or [] if item.get("id") in priority_ids),
            None,
        )
        reason = (
            f"Objetivo priorizado: {goal.get('name')}; funding gap: {goal.get('funding_gap')}; "
            f"deadline: {goal.get('deadline')}."
            if goal
            else summary
        )
    elif policy_state == "INVESTMENT_READY":
        reason = (
            "As prioridades prudenciais conhecidas foram atendidas; capacidade de investimento "
            f"observada: {metrics.get('investment_capacity')}."
        )
    else:
        reason = (
            "A construção permanece limitada pelos fatores: "
            + (", ".join(readiness_limiters) if readiness_limiters else "nenhum bloqueio crítico")
            + "."
        )
    return [
        {
            "code": "PRIMARY_POLICY_DECISION",
            "decision": decision,
            "reason": reason,
            "evidence_refs": evidence_refs,
            "rule_ids": list(dict.fromkeys(triggered_rule_ids)),
            "blocked_alternatives": (
                ["INVEST_SURPLUS_CAPITAL"] if readiness != "READY" else []
            ),
        },
        {
            "code": "INVESTMENT_READINESS_DECISION",
            "decision": readiness,
            "reason": (
                "Novos investimentos estão liberados apenas como capital excedente."
                if readiness == "READY"
                else "Novos investimentos permanecem limitados ou bloqueados pelas prioridades e evidências listadas."
            ),
            "evidence_refs": ["INVESTMENT_CAPACITY", "READINESS_LIMITERS"],
            "rule_ids": ["FPV1-READY-001"],
            "blocked_alternatives": (
                [] if readiness == "READY" else ["FULL_NEW_INVESTMENT"]
            ),
        },
    ]


def _member_policy_views(
    state: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    household_id: int,
    evaluated_at: datetime,
    consolidated_state: str,
    consolidated_readiness: str,
) -> list[dict[str, Any]]:
    """Expose policy signals over the personal metrics already produced by State v1.

    Household-owned values deliberately remain only in the consolidated view.
    A shared-household member therefore never receives a fabricated READY status
    from an incomplete personal slice.
    """

    raw_views = list(state.get("member_views") or [])
    household = context.get("household") or {}
    personal_household = (
        str(household.get("household_type", "")).upper() == "PERSONAL"
        and len(raw_views) == 1
    )
    personal_debts = _active_context_records(
        context,
        "liabilities",
        {"ACTIVE", "DEFAULTED"},
        household_id=household_id,
    )
    results: list[dict[str, Any]] = []
    for raw in sorted(raw_views, key=lambda item: _stable_identifier_key(item.get("user_id"))):
        view = dict(raw)
        user_id = int(view["user_id"])
        metrics = dict(view.get("metrics") or {})
        goals = list(view.get("goals") or [])
        missing = list(view.get("missing_fields") or [])
        inconsistencies = list(view.get("inconsistencies") or [])
        signals: list[str] = []
        critical_missing = [field for field in CRITICAL_DECISION_FIELDS if metrics.get(field) is None]
        disposable = _decimal(metrics.get("disposable_income"))
        savings = _decimal(metrics.get("savings_capacity"))
        cash_flow = _decimal(metrics.get("cash_flow"))
        reserve = _decimal(metrics.get("emergency_reserve"))
        reserve_months = _decimal(metrics.get("emergency_reserve_months"))
        debt_service_ratio = _decimal(metrics.get("debt_service_ratio"))
        net_worth = _decimal(metrics.get("net_worth"))
        member_debts = [
            item
            for item in personal_debts
            if str(item.get("ownership_scope", "")).upper() == "PERSONAL"
            and int(item.get("user_id")) == user_id
        ]
        member_debt_due_priority = any(
            (due_date := _as_date(item.get("due_date"))) is not None
            and (due_date - evaluated_at.date()).days <= RULES.near_term_debt_days
            and (
                (balance := _decimal(item.get("current_balance"))) is None
                or balance > 0
            )
            for item in member_debts
        )
        debt_priority = bool(
            (debt_service_ratio is not None and debt_service_ratio >= RULES.debt_service_priority_pct)
            or (net_worth is not None and net_worth < 0)
            or any(str(item.get("status", "")).upper() == "DEFAULTED" for item in member_debts)
            or any(
                (rate := _decimal(item.get("annual_interest_rate_pct"))) is not None
                and rate >= RULES.known_high_cost_debt_apr_pct
                for item in member_debts
            )
            or member_debt_due_priority
        )
        cash_recovery = bool(
            (disposable is not None and disposable <= 0)
            or (savings is not None and savings <= 0)
            or (cash_flow is not None and cash_flow < 0)
        )
        reserve_priority = bool(
            reserve == 0
            or (
                reserve_months is not None
                and reserve_months < RULES.reserve_base_months
            )
        )
        goal_priority = False
        for goal in goals:
            gap = _decimal(goal.get("funding_gap"))
            if gap is None or gap <= 0 or str(goal.get("status", "ACTIVE")).upper() != "ACTIVE":
                continue
            priority = str(goal.get("priority", "LOW")).upper()
            deadline = _as_date(goal.get("deadline"))
            days = (deadline - evaluated_at.date()).days if deadline else None
            if (
                priority == "HIGH"
                or (days is not None and days <= RULES.urgent_goal_days)
                or (priority == "MEDIUM" and days is not None and days <= RULES.near_term_goal_days)
            ):
                goal_priority = True
                break
        if inconsistencies or critical_missing:
            signals.append("COMPLETE_CRITICAL_DATA")
        if cash_recovery:
            signals.append("STABILIZE_CASH_FLOW")
        if debt_priority:
            signals.append("REDUCE_DEBT_BURDEN")
        if reserve_priority:
            signals.append("BUILD_EMERGENCY_RESERVE")
        if goal_priority:
            signals.append("FUND_PRIORITY_GOAL")
        if not signals:
            signals.append("COMPLETE_READINESS_DATA")

        if personal_household:
            member_state = consolidated_state
            member_readiness = consolidated_readiness
            explanation = "Esta visão pessoal coincide com o household individual canônico."
        elif inconsistencies or critical_missing:
            member_state = "DATA_BLOCKED"
            member_readiness = "BLOCKED"
            explanation = "A visão pessoal possui dados críticos ausentes ou inconsistentes."
        elif cash_recovery:
            member_state = "CASHFLOW_RECOVERY"
            member_readiness = "BLOCKED"
            explanation = "A visão pessoal indica recuperação de fluxo de caixa como prioridade."
        elif debt_priority:
            member_state = "DEBT_PRIORITY"
            member_readiness = "LIMITED"
            explanation = "A visão pessoal indica pressão de dívida, sem incluir valores compartilhados."
        elif reserve_priority:
            member_state = "EMERGENCY_RESERVE_PRIORITY"
            member_readiness = "LIMITED"
            explanation = "A reserva pessoal conhecida está abaixo do piso prudencial da política."
        elif goal_priority:
            member_state = "GOAL_PRIORITY"
            member_readiness = "LIMITED"
            explanation = "Um objetivo pessoal conhecido exige prioridade."
        else:
            member_state = "BALANCED_BUILD"
            member_readiness = "LIMITED"
            explanation = "Visão pessoal parcial; valores HOUSEHOLD permanecem na decisão consolidada."
        member_missing = list(missing)
        if not personal_household:
            member_missing.append("household.shared_values_excluded_from_personal_view")
        results.append(
            {
                "user_id": user_id,
                "full_name": view.get("full_name"),
                "scope": "PERSONAL_ONLY",
                "policy_state": member_state,
                "investment_readiness": member_readiness,
                "priority_signals": sorted(
                    set(signals), key=lambda code: PRIORITY_ORDER[code]
                ),
                "metrics": metrics,
                "goals": goals,
                "missing_information": list(dict.fromkeys(member_missing)),
                "inconsistencies": inconsistencies,
                "explanation": explanation,
            }
        )
    return results


def calculate_financial_policy(
    financial_state: Mapping[str, Any],
    *,
    normalized_inputs: Mapping[str, Any],
    previous_financial_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive a safe, explainable priority policy from Financial State v1.

    This pure function never reads a database, uses the wall clock, recomputes
    Financial State metrics, allocates securities, or mutates its inputs.
    """

    state = deepcopy(dict(financial_state))
    context = deepcopy(dict(normalized_inputs or {}))
    previous_state = (
        deepcopy(dict(previous_financial_state))
        if previous_financial_state is not None
        else None
    )
    try:
        household_id = int(state["household_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("financial_state.household_id is required") from exc
    evaluated_at = _as_datetime(state.get("evaluated_at"))
    metrics = dict(state.get("metrics") or {})
    source_version = str(state.get("engine_version") or "")
    quality = str(state.get("data_quality") or "")
    try:
        confidence = int(state.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1

    traces: list[dict[str, Any]] = []
    data_blockers: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    readiness_limiters: list[str] = []

    version_ok = source_version == SUPPORTED_FINANCIAL_STATE_VERSION
    traces.append(
        _trace(
            "FPV1-DATA-001",
            "NOT_TRIGGERED" if version_ok else "TRIGGERED",
            observed_values={"source_engine_version": source_version},
            thresholds={"supported_engine_version": SUPPORTED_FINANCIAL_STATE_VERSION},
            explanation="A política aceita somente o contrato canônico explicitamente versionado.",
        )
    )
    if not version_ok:
        data_blockers.append(
            _message(
                "UNSUPPORTED_FINANCIAL_STATE_VERSION",
                "A versão do Financial State não é suportada por esta política.",
                fields=("engine_version",),
                rule_ids=("FPV1-DATA-001",),
            )
        )

    context_household = context.get("household") or {}
    context_household_raw = (
        context_household.get("id") if isinstance(context_household, Mapping) else None
    )
    context_household_id: int | None
    try:
        context_household_id = (
            int(context_household_raw) if context_household_raw is not None else None
        )
    except (TypeError, ValueError):
        context_household_id = None
    context_missing = not context or context_household_raw is None
    context_mismatch = (
        not context_missing
        and (context_household_id is None or context_household_id != household_id)
    )
    traces.append(
        _trace(
            "FPV1-DATA-007",
            "TRIGGERED" if context_missing or context_mismatch else "NOT_TRIGGERED",
            observed_values={
                "financial_state_household_id": household_id,
                "normalized_inputs_household_id": context_household_raw,
            },
            explanation="O contexto detalhado é obrigatório e não pode cruzar households.",
        )
    )
    if context_missing:
        data_blockers.append(
            _message(
                "POLICY_CONTEXT_MISSING",
                "O contexto normalizado do Financial State é necessário para uma política segura.",
                fields=("normalized_inputs.household.id",),
                rule_ids=("FPV1-DATA-007",),
            )
        )
    elif context_mismatch:
        data_blockers.append(
            _message(
                "FINANCIAL_STATE_CONTEXT_MISMATCH",
                "O Financial State e seu contexto normalizado não pertencem ao mesmo household.",
                fields=("household_id", "normalized_inputs.household.id"),
                rule_ids=("FPV1-DATA-007",),
            )
        )

    source_inconsistencies = list(state.get("inconsistencies") or [])
    quality_blocked = (
        quality in {"INSUFFICIENT", "INCONSISTENT"}
        or quality
        not in {"COMPLETE", "PARTIAL", "STALE", "INSUFFICIENT", "INCONSISTENT"}
        or bool(source_inconsistencies)
    )
    traces.append(
        _trace(
            "FPV1-DATA-002",
            "TRIGGERED" if quality_blocked else "NOT_TRIGGERED",
            observed_values={
                "data_quality": quality,
                "inconsistencies": source_inconsistencies,
            },
            explanation="Qualidade insegura bloqueia; PARTIAL é avaliada pelos campos concretos.",
        )
    )
    if quality_blocked:
        data_blockers.append(
            _message(
                "UNSAFE_DATA_QUALITY",
                "A qualidade dos dados ainda não permite ordenar prioridades com segurança.",
                fields=("data_quality",),
                rule_ids=("FPV1-DATA-002",),
            )
        )
    if quality != "COMPLETE":
        readiness_limiters.append("SOURCE_QUALITY_NOT_COMPLETE")

    confidence_valid = 0 <= confidence <= 100
    confidence_blocked = (
        not confidence_valid or confidence < RULES.minimum_policy_confidence
    )
    traces.append(
        _trace(
            "FPV1-DATA-003",
            "TRIGGERED" if confidence_blocked else "NOT_TRIGGERED",
            observed_values={"confidence": confidence},
            thresholds={
                "minimum_policy_confidence": RULES.minimum_policy_confidence,
                "minimum_ready_confidence": RULES.minimum_ready_confidence,
            },
            explanation="Confidence mede completude dos dados, não probabilidade de mercado.",
        )
    )
    if confidence_blocked:
        data_blockers.append(
            _message(
                (
                    "CONFIDENCE_BELOW_POLICY_MINIMUM"
                    if confidence_valid
                    else "CONFIDENCE_OUT_OF_RANGE"
                ),
                (
                    "A completude dos dados está abaixo do mínimo prudencial da política."
                    if confidence_valid
                    else "O confidence do Financial State está fora do intervalo válido de 0 a 100."
                ),
                fields=("confidence",),
                rule_ids=("FPV1-DATA-003",),
            )
        )
    if confidence < RULES.minimum_ready_confidence:
        readiness_limiters.append("CONFIDENCE_BELOW_READY_MINIMUM")

    decision_missing = [
        field for field in CRITICAL_DECISION_FIELDS if metrics.get(field) is None
    ]
    traces.append(
        _trace(
            "FPV1-DATA-004",
            "TRIGGERED" if decision_missing else "NOT_TRIGGERED",
            observed_values={"critical_missing_fields": decision_missing},
            explanation="Ausência permaneceu desconhecida; nenhum campo crítico recebeu zero implícito.",
        )
    )
    if decision_missing:
        data_blockers.append(
            _message(
                "DECISION_CORE_MISSING",
                "Informe renda e despesas essenciais antes de gerar uma política segura.",
                fields=tuple(f"metrics.{field}" for field in decision_missing),
                rule_ids=("FPV1-DATA-004",),
            )
        )

    stale_fields = list(state.get("stale_fields") or [])
    provenance = dict(state.get("provenance") or {})
    stale_profile_income = bool(
        provenance.get("recurring_monthly_income", {}).get("financial_profile_fallback_user_ids")
        and any(str(field).startswith("financial_profiles.") for field in stale_fields)
    )
    critical_stale = [field for field in stale_fields if field in {"incomes", "expenses"}]
    if stale_profile_income:
        critical_stale.extend(field for field in stale_fields if str(field).startswith("financial_profiles."))
    critical_stale = list(dict.fromkeys(critical_stale))
    traces.append(
        _trace(
            "FPV1-DATA-005",
            "TRIGGERED" if critical_stale else "NOT_TRIGGERED",
            observed_values={"critical_stale_fields": critical_stale, "all_stale_fields": stale_fields},
            explanation="Somente staleness que afeta renda ou despesa bloqueia toda a decisão.",
        )
    )
    if critical_stale:
        data_blockers.append(
            _message(
                "CASHFLOW_DATA_STALE",
                "Atualize renda e despesas antes de definir novas prioridades.",
                fields=tuple(critical_stale),
                rule_ids=("FPV1-DATA-005",),
            )
        )
    if stale_fields:
        readiness_limiters.append("STALE_DATA_PRESENT")
        warnings.append(
            _message(
                "STALE_DATA_PRESENT",
                "Há informações desatualizadas; a prontidão para investir foi limitada.",
                fields=tuple(stale_fields),
                rule_ids=("FPV1-DATA-005",),
            )
        )

    currencies, currency_fields, missing_currency_fields = _currency_gate(
        context, household_id=household_id
    )
    currency_blocked = any(currency != "BRL" for currency in currencies)
    currency_unknown = bool(missing_currency_fields)
    traces.append(
        _trace(
            "FPV1-DATA-006",
            "TRIGGERED"
            if currency_blocked or currency_unknown
            else "NOT_TRIGGERED",
            observed_values={
                "currencies": currencies,
                "missing_currency_fields": missing_currency_fields,
            },
            thresholds={
                "supported_aggregate_currencies": SUPPORTED_AGGREGATE_CURRENCIES
            },
            explanation="A política não converte moedas nem presume taxas de câmbio.",
        )
    )
    if currency_blocked:
        data_blockers.append(
            _message(
                "UNSUPPORTED_CURRENCY_AGGREGATION",
                "Existem valores em moeda não comparável sem conversão explícita.",
                fields=tuple(currency_fields),
                rule_ids=("FPV1-DATA-006",),
            )
        )
    if currency_unknown:
        data_blockers.append(
            _message(
                "CURRENCY_MISSING",
                "Há valores patrimoniais sem moeda informada; BRL não foi presumido.",
                fields=tuple(missing_currency_fields),
                rule_ids=("FPV1-DATA-006",),
            )
        )

    readiness_fields = list(READINESS_CORE_FIELDS)
    total_expenses = _decimal(metrics.get("total_expenses"))
    total_liabilities = _decimal(metrics.get("total_liabilities"))
    if total_expenses is not None and total_expenses > 0:
        readiness_fields.append("emergency_reserve_months")
    if total_liabilities is None or total_liabilities > 0:
        readiness_fields.append("monthly_debt_service")
    readiness_missing = [field for field in readiness_fields if metrics.get(field) is None]
    if readiness_missing:
        readiness_limiters.append("READINESS_CORE_MISSING")
        warnings.append(
            _message(
                "READINESS_CORE_MISSING",
                "A ordem principal pode ser avaliada, mas faltam dados para liberar novos investimentos.",
                fields=tuple(f"metrics.{field}" for field in readiness_missing),
            )
        )
    missing_fields = list(state.get("missing_fields") or [])
    goals_unknown = "goals" in missing_fields
    if goals_unknown:
        readiness_limiters.append("GOALS_NOT_DECLARED")
        warnings.append(
            _message(
                "GOALS_NOT_DECLARED",
                "Objetivos financeiros ainda não foram declarados; a prontidão permanece limitada.",
                fields=("goals",),
                rule_ids=("FPV1-GOAL-001", "FPV1-GOAL-002"),
            )
        )
    debt_policy = _debt_policy(
        metrics,
        context,
        household_id=household_id,
        evaluated_at=evaluated_at,
        traces=traces,
        warnings=warnings,
        limitations=limitations,
    )
    if debt_policy["unknown_rate_debt_ids"]:
        readiness_limiters.append("ACTIVE_DEBT_RATE_UNKNOWN")
    if debt_policy["zero_balance_payment_debt_ids"]:
        readiness_limiters.append("DEBT_BALANCE_PAYMENT_INCONSISTENT")
    reserve_policy = _reserve_policy(metrics, traces=traces, limitations=limitations)
    if reserve_policy["status"] == "UNKNOWN":
        readiness_limiters.append("RESERVE_ADEQUACY_UNKNOWN")
    if reserve_policy["target_completeness"] == "PARTIAL":
        readiness_limiters.append("RESERVE_TARGET_CONTEXT_PARTIAL")
    goal_policy = _goal_policy(
        state,
        evaluated_at,
        goals_declared=not goals_unknown,
        traces=traces,
        warnings=warnings,
        limitations=limitations,
    )
    if goal_policy["unknown_gap_goal_ids"]:
        readiness_limiters.append("GOAL_PROGRESS_UNKNOWN")
    if goal_policy["unknown_deadline_unfunded_goal_ids"]:
        readiness_limiters.append("GOAL_DEADLINE_UNKNOWN")

    disposable = _decimal(metrics.get("disposable_income"))
    savings_capacity = _decimal(metrics.get("savings_capacity"))
    cash_flow = _decimal(metrics.get("cash_flow"))
    cashflow_recovery = bool(
        (disposable is not None and disposable <= 0)
        or (savings_capacity is not None and savings_capacity <= 0)
        or (cash_flow is not None and cash_flow < 0)
    )
    traces.append(
        _trace(
            "FPV1-CASH-001",
            "TRIGGERED"
            if cashflow_recovery
            else ("NOT_EVALUATED" if decision_missing else "NOT_TRIGGERED"),
            observed_values={
                "cash_flow": cash_flow,
                "disposable_income": disposable,
                "savings_capacity": savings_capacity,
            },
            thresholds={"minimum_positive_value": Decimal("0.00")},
            explanation="Valores explicitamente iguais a zero são conhecidos e não foram confundidos com ausência.",
        )
    )

    deterioration_signals: list[str] = []
    previous_evaluated_at: datetime | None = None
    previous_state_valid = False
    if previous_state is None:
        limitations.append(
            _message(
                "FINANCIAL_TREND_HISTORY_NOT_AVAILABLE",
                "Não há snapshot anterior comparável; nenhuma tendência histórica foi presumida.",
            )
        )
    else:
        try:
            previous_household_id = int(previous_state.get("household_id"))
            previous_evaluated_at = _as_datetime(previous_state.get("evaluated_at"))
            previous_state_valid = (
                previous_household_id == household_id
                and previous_state.get("engine_version")
                == SUPPORTED_FINANCIAL_STATE_VERSION
                and previous_evaluated_at < evaluated_at
            )
        except (TypeError, ValueError):
            previous_state_valid = False
        if previous_state_valid:
            deterioration_signals = _cashflow_deterioration(
                metrics, dict(previous_state.get("metrics") or {})
            )
        else:
            limitations.append(
                _message(
                    "FINANCIAL_TREND_HISTORY_NOT_COMPARABLE",
                    "O snapshot anterior não é comparável por household, versão ou timestamp.",
                )
            )
    traces.append(
        _trace(
            "FPV1-CASH-002",
            (
                "TRIGGERED"
                if deterioration_signals
                else "NOT_TRIGGERED"
                if previous_state_valid
                else "NOT_EVALUATED"
            ),
            observed_values={
                "previous_evaluated_at": previous_evaluated_at,
                "boundary_crossings": deterioration_signals,
            },
            thresholds={"positive_to_non_positive_boundary": Decimal("0.00")},
            explanation="Deterioração só foi declarada quando um snapshot anterior comparável cruzou o limite de caixa seguro.",
        )
    )
    if deterioration_signals:
        cashflow_recovery = True
        warnings.append(
            _message(
                "CASHFLOW_DETERIORATION_DETECTED",
                "O fluxo financeiro cruzou de positivo para não positivo desde o snapshot anterior.",
                fields=tuple(f"metrics.{field}" for field in deterioration_signals),
                rule_ids=("FPV1-CASH-002",),
            )
        )

    investment_capacity = _decimal(metrics.get("investment_capacity"))
    if data_blockers or cashflow_recovery or debt_policy["investment_blocking"] or reserve_policy["status"] == "ABSENT":
        readiness = "BLOCKED"
    elif investment_capacity is None or investment_capacity <= 0:
        readiness = "BLOCKED"
    elif (
        readiness_limiters
        or debt_policy["priority_required"]
        or reserve_policy["status"] in {"UNKNOWN", "BUILDING"}
        or goal_policy["priority_required"]
    ):
        readiness = "LIMITED"
    else:
        readiness = "READY"

    if data_blockers:
        policy_state = "DATA_BLOCKED"
    elif cashflow_recovery:
        policy_state = "CASHFLOW_RECOVERY"
    elif debt_policy["priority_required"]:
        policy_state = "DEBT_PRIORITY"
    elif reserve_policy["status"] in {"ABSENT", "BUILDING"}:
        policy_state = "EMERGENCY_RESERVE_PRIORITY"
    elif goal_policy["priority_required"]:
        policy_state = "GOAL_PRIORITY"
    elif readiness == "READY":
        policy_state = "INVESTMENT_READY"
    else:
        policy_state = "BALANCED_BUILD"

    if cashflow_recovery:
        blockers.append(
            _message(
                "NON_POSITIVE_CASHFLOW",
                "Recupere um fluxo de caixa positivo antes de destinar capital novo a investimentos.",
                fields=("metrics.disposable_income", "metrics.savings_capacity", "metrics.cash_flow"),
                rule_ids=("FPV1-CASH-001", "FPV1-CASH-002"),
            )
        )
    if debt_policy["investment_blocking"]:
        blockers.append(
            _message(
                "DEBT_REQUIRES_IMMEDIATE_PRIORITY",
                "A pressão ou o custo conhecido das dívidas deve ser tratado antes de novos investimentos.",
                fields=("metrics.debt_service_ratio",),
                rule_ids=("FPV1-DEBT-001", "FPV1-DEBT-002", "FPV1-DEBT-003"),
            )
        )
    if reserve_policy["status"] == "ABSENT":
        blockers.append(
            _message(
                "EMERGENCY_RESERVE_ABSENT",
                "A reserva de emergência conhecida é zero e deve ser iniciada primeiro.",
                fields=("metrics.emergency_reserve",),
                rule_ids=("FPV1-RESERVE-002",),
            )
        )
    if investment_capacity is None:
        blockers.append(
            _message(
                "INVESTMENT_CAPACITY_UNKNOWN",
                "A capacidade de investimento é desconhecida; novos aportes não podem ser liberados.",
                fields=("metrics.investment_capacity",),
                rule_ids=("FPV1-READY-001",),
            )
        )
    elif investment_capacity <= 0:
        blockers.append(
            _message(
                "NO_INVESTMENT_CAPACITY",
                "Não há capacidade financeira positiva disponível para novos investimentos.",
                fields=("metrics.investment_capacity",),
                rule_ids=("FPV1-READY-001",),
            )
        )
    blockers = _dedupe_messages([*data_blockers, *blockers])
    warnings = _dedupe_messages(warnings)
    limitations = _dedupe_messages(limitations)
    readiness_limiters = list(dict.fromkeys(readiness_limiters))

    priorities: list[dict[str, Any]] = []
    if data_blockers:
        priorities.append(
            _priority(
                "COMPLETE_CRITICAL_DATA",
                "Completar dados financeiros críticos",
                "Corrija ou atualize os dados indicados antes de aplicar qualquer política financeira.",
                "ACTIVE",
                ["DATA_QUALITY", "CONFIDENCE"],
            )
        )
    if cashflow_recovery:
        priorities.append(
            _priority(
                "STABILIZE_CASH_FLOW",
                "Estabilizar o fluxo de caixa",
                "Leve a renda disponível e a capacidade de poupança para um valor positivo.",
                "ACTIVE" if not data_blockers else "NEXT",
                ["DISPOSABLE_INCOME", "SAVINGS_CAPACITY"],
            )
        )
    if debt_policy["priority_required"]:
        priorities.append(
            _priority(
                "REDUCE_DEBT_BURDEN",
                "Reduzir a pressão das dívidas",
                "Priorize passivos sinalizados por default, custo conhecido, pressão mensal, vencimento ou patrimônio líquido negativo.",
                "ACTIVE" if policy_state == "DEBT_PRIORITY" else "NEXT",
                ["TOTAL_LIABILITIES", "NET_WORTH", "DEBT_SERVICE_RATIO"],
            )
        )
    if reserve_policy["status"] in {"ABSENT", "BUILDING"}:
        priorities.append(
            _priority(
                "BUILD_EMERGENCY_RESERVE",
                "Fortalecer a reserva de emergência",
                "Aproxime a reserva do alvo dinâmico calculado com o contexto conhecido.",
                "ACTIVE" if policy_state == "EMERGENCY_RESERVE_PRIORITY" else "NEXT",
                ["EMERGENCY_RESERVE", "RESERVE_TARGET"],
            )
        )
    if goal_policy["priority_required"]:
        priorities.append(
            _priority(
                "FUND_PRIORITY_GOAL",
                "Financiar o objetivo prioritário",
                "Direcione capacidade disponível aos objetivos explicitamente prioritários ou próximos.",
                "ACTIVE" if policy_state == "GOAL_PRIORITY" else "NEXT",
                ["PRIORITY_GOALS"],
            )
        )
    if readiness_limiters:
        priorities.append(
            _priority(
                "COMPLETE_READINESS_DATA",
                "Completar dados de prontidão",
                "Confirme reserva, dívidas, patrimônio e objetivos antes de liberar integralmente novos aportes.",
                "ACTIVE" if not priorities else "NEXT",
                ["READINESS_MISSING_FIELDS", "READINESS_LIMITERS"],
            )
        )
    priorities.append(
        _priority(
            "INVEST_SURPLUS_CAPITAL",
            "Investir somente o capital excedente",
            "Esta etapa indica apenas prontidão financeira; ativos, mercados e quantidades não são escolhidos aqui.",
            "ACTIVE" if readiness == "READY" else ("CONDITIONAL" if readiness == "LIMITED" else "BLOCKED"),
            ["INVESTMENT_CAPACITY"],
        )
    )
    priorities.sort(key=lambda item: PRIORITY_ORDER[item["code"]])
    for rank, item in enumerate(priorities, start=1):
        item["rank"] = rank

    summaries = {
        "DATA_BLOCKED": "Complete os dados críticos antes de definir prioridades financeiras.",
        "CASHFLOW_RECOVERY": "A prioridade atual é recuperar e estabilizar o fluxo de caixa.",
        "DEBT_PRIORITY": "A prioridade atual é reduzir a pressão das dívidas identificadas.",
        "EMERGENCY_RESERVE_PRIORITY": "A prioridade atual é fortalecer a reserva de emergência.",
        "GOAL_PRIORITY": "Um objetivo financeiro requer prioridade antes de ampliar investimentos de risco.",
        "BALANCED_BUILD": "A situação permite construção gradual, mas ainda existem limitações para aportes plenos.",
        "INVESTMENT_READY": "Os dados conhecidos permitem destinar capital excedente a investimentos.",
    }
    traces.append(
        _trace(
            "FPV1-READY-001",
            "TRIGGERED" if readiness == "READY" else "NOT_TRIGGERED",
            observed_values={
                "policy_state": policy_state,
                "investment_capacity": investment_capacity,
                "reserve_status": reserve_policy["status"],
                "readiness_limiters": readiness_limiters,
            },
            thresholds={"minimum_ready_confidence": RULES.minimum_ready_confidence},
            explanation="Prontidão não é recomendação de ativo e respeita todas as prioridades anteriores.",
        )
    )

    evidence = [
        _evidence("DATA_QUALITY", "Qualidade dos dados", quality, "STATE", "financial_state.data_quality"),
        _evidence("CONFIDENCE", "Confidence dos dados", confidence, "PERCENT", "financial_state.confidence"),
        _evidence("DISPOSABLE_INCOME", "Renda disponível", disposable, "BRL", "financial_state.metrics.disposable_income"),
        _evidence("SAVINGS_CAPACITY", "Capacidade de poupança", savings_capacity, "BRL", "financial_state.metrics.savings_capacity"),
        _evidence("INVESTMENT_CAPACITY", "Capacidade de investimento", investment_capacity, "BRL", "financial_state.metrics.investment_capacity"),
        _evidence("TOTAL_ASSETS", "Ativos totais", _decimal(metrics.get("total_assets")), "BRL", "financial_state.metrics.total_assets"),
        _evidence("TOTAL_LIABILITIES", "Passivos totais", total_liabilities, "BRL", "financial_state.metrics.total_liabilities"),
        _evidence("NET_WORTH", "Patrimônio líquido", _decimal(metrics.get("net_worth")), "BRL", "financial_state.metrics.net_worth"),
        _evidence("DEBT_SERVICE_RATIO", "Comprometimento mensal com dívidas", _decimal(metrics.get("debt_service_ratio")), "PERCENT", "financial_state.metrics.debt_service_ratio"),
        _evidence("EMERGENCY_RESERVE", "Reserva de emergência", _decimal(metrics.get("emergency_reserve")), "BRL", "financial_state.metrics.emergency_reserve"),
        _evidence("RESERVE_TARGET", "Alvo dinâmico de reserva", reserve_policy["target_months"], "MONTHS", "financial_policy.reserve_policy.target_months"),
        _evidence("PRIORITY_GOALS", "Objetivos que requerem prioridade", len(goal_policy["priority_goal_ids"]), "COUNT", "financial_policy.goal_policy.priority_goal_ids"),
        _evidence("READINESS_MISSING_FIELDS", "Dados de prontidão ausentes", readiness_missing, "FIELDS", "financial_policy.data_gate.readiness_missing_fields"),
        _evidence("READINESS_LIMITERS", "Limitadores de prontidão", readiness_limiters, "CODES", "financial_policy.data_gate.readiness_limiters"),
        _evidence("CASHFLOW_DETERIORATION", "Deterioração de caixa observada", deterioration_signals, "FIELDS", "financial_policy.history.boundary_crossings"),
    ]

    source_missing_fields = list(state.get("missing_fields") or [])
    information_messages = [*blockers, *warnings, *limitations]
    if source_missing_fields:
        information_messages.append(
            _message(
                "FINANCIAL_STATE_FIELDS_MISSING",
                "Informações ausentes no Financial State podem alterar a política quando forem fornecidas.",
                fields=tuple(source_missing_fields),
            )
        )
    missing_information = _dedupe_messages(
        item
        for item in information_messages
        if str(item.get("code")) in MISSING_INFORMATION_CODES
    )
    explanations = _policy_explanations(
        policy_state=policy_state,
        readiness=readiness,
        summary=summaries[policy_state],
        priorities=priorities,
        metrics=metrics,
        debt_policy=debt_policy,
        reserve_policy=reserve_policy,
        goal_policy=goal_policy,
        blockers=blockers,
        readiness_limiters=readiness_limiters,
        traces=traces,
    )
    member_policy_views = _member_policy_views(
        state,
        context,
        household_id=household_id,
        evaluated_at=evaluated_at,
        consolidated_state=policy_state,
        consolidated_readiness=readiness,
    )

    gate_status = "BLOCKED" if data_blockers else ("LIMITED" if readiness_limiters else "PASS")
    input_fingerprint = _fingerprint(state, context, previous_state)
    ruleset_fingerprint = _ruleset_fingerprint()
    data_gate = {
        "status": gate_status,
        "critical_missing_fields": decision_missing,
        "readiness_missing_fields": readiness_missing,
        "critical_stale_fields": critical_stale,
        "currencies": currencies,
        "missing_currency_fields": missing_currency_fields,
        "readiness_limiters": readiness_limiters,
    }
    ruleset = {
        "version": RULES_VERSION,
        "thresholds": RULES.public_thresholds(),
    }
    decision_fingerprint = decision_fingerprint_from_payload(
        {
            "input_fingerprint": input_fingerprint,
            "ruleset_fingerprint": ruleset_fingerprint,
            "policy_state": policy_state,
            "investment_readiness": readiness,
            "summary": summaries[policy_state],
            "priority_stack": priorities,
            "data_gate": data_gate,
            "debt_policy": debt_policy,
            "reserve_policy": reserve_policy,
            "goal_policy": goal_policy,
            "blockers": blockers,
            "warnings": warnings,
            "limitations": limitations,
            "missing_information": missing_information,
            "explanations": explanations,
            "evidence": evidence,
            "member_policy_views": member_policy_views,
            "rules_evaluated": traces,
        }
    )
    return {
        "policy_id": None,
        "household_id": household_id,
        "financial_state_snapshot_id": state.get("snapshot_id"),
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "evaluated_at": evaluated_at,
        "generated_at": evaluated_at,
        "created_at": None,
        "input_fingerprint": input_fingerprint,
        "ruleset_fingerprint": ruleset_fingerprint,
        "decision_fingerprint": decision_fingerprint,
        "policy_state": policy_state,
        "investment_readiness": readiness,
        "summary": summaries[policy_state],
        "priority_stack": priorities,
        "data_gate": data_gate,
        "debt_policy": debt_policy,
        "reserve_policy": reserve_policy,
        "goal_policy": goal_policy,
        "blockers": blockers,
        "warnings": warnings,
        "limitations": limitations,
        "missing_information": missing_information,
        "explanations": explanations,
        "evidence": evidence,
        "member_policy_views": member_policy_views,
        "rules_evaluated": traces,
        "ruleset": ruleset,
        "source_financial_state": {
            "engine_version": source_version,
            "evaluated_at": evaluated_at,
            "data_quality": quality,
            "confidence": confidence,
            "snapshot_id": state.get("snapshot_id"),
        },
        "previous_financial_state": {
            "available": previous_state is not None,
            "comparable": previous_state_valid,
            "evaluated_at": previous_evaluated_at,
            "boundary_crossings": deterioration_signals,
            "snapshot_id": (
                previous_state.get("snapshot_id") if previous_state is not None else None
            ),
        },
    }

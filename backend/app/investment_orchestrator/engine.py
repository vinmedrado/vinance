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
from backend.app.financial_policy.engine import (
    decision_fingerprint_from_payload as policy_fingerprint_from_payload,
)
from backend.app.investment_orchestrator.rules import (
    CONCENTRATION_THRESHOLD_PCT,
    ENGINE_VERSION,
    MONEY_QUANTUM,
    MONEY_ROUNDING,
    PROFILE_ORDER,
    RULE_CATALOG,
    RULES,
    RULES_VERSION,
    SETTLEMENT_CURRENCY,
    SUPPORTED_MARKETS,
    UNSUPPORTED_CLASSES,
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
    semantic = _semantic(
        payload,
        "orchestration_id",
        "financial_state_snapshot_id",
        "financial_policy_decision_id",
        "capital_allocation_decision_id",
        "decision_fingerprint",
        "generated_at",
        "created_at",
    )
    return _sha256(semantic)


def _money(value: Any, *, allow_none: bool = False) -> Decimal | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError("monetary value is required")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("monetary value must be finite") from exc
    if not decimal.is_finite():
        raise ValueError("monetary value must be finite")
    return decimal.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


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


def _dedupe(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        fields = tuple(str(value) for value in item.get("fields") or [])
        key = (str(item.get("code")), fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _trace(
    rule_id: str,
    outcome: str,
    observed: Mapping[str, Any],
    explanation: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_version": RULES_VERSION,
        "description": RULE_CATALOG[rule_id],
        "outcome": outcome,
        "observed_values": dict(observed),
        "rule_parameters": {
            "settlement_currency": SETTLEMENT_CURRENCY,
            "market_freshness_days": RULES.market_freshness_days,
            "concentration_threshold_pct": CONCENTRATION_THRESHOLD_PCT,
        },
        "explanation": explanation,
    }


def _ruleset_fingerprint() -> str:
    return _sha256(
        {
            "engine_version": ENGINE_VERSION,
            "rules_version": RULES_VERSION,
            "rules": RULES.__dict__,
            "rule_catalog": RULE_CATALOG,
            "supported_markets": SUPPORTED_MARKETS,
            "unsupported_classes": UNSUPPORTED_CLASSES,
            "profile_order": PROFILE_ORDER,
        }
    )


def _validate_chain(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    allocation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if state.get("engine_version") != "household-financial-state-v1":
        blockers.append(
            _message(
                "STATE_VERSION_INVALID",
                "O Financial State não usa a versão canônica esperada.",
                fields=("financial_state.engine_version",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    if policy.get("engine_version") != "financial-policy-v1":
        blockers.append(
            _message(
                "POLICY_VERSION_INVALID",
                "A Financial Policy não usa a versão canônica esperada.",
                fields=("financial_policy.engine_version",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    if allocation.get("engine_version") != "capital-allocation-v1":
        blockers.append(
            _message(
                "ALLOCATION_VERSION_INVALID",
                "A Capital Allocation não usa a versão canônica esperada.",
                fields=("capital_allocation.engine_version",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    household_ids = {
        value
        for value in (
            state.get("household_id"),
            policy.get("household_id"),
            allocation.get("household_id"),
        )
        if value is not None
    }
    if len(household_ids) != 1:
        blockers.append(
            _message(
                "HOUSEHOLD_CHAIN_MISMATCH",
                "State, Policy e Allocation não pertencem ao mesmo household.",
                fields=("household_id",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    state_id = state.get("snapshot_id")
    policy_state_id = policy.get("financial_state_snapshot_id")
    allocation_state_id = allocation.get("financial_state_snapshot_id")
    persisted_state_ids = {
        value for value in (state_id, policy_state_id, allocation_state_id) if value is not None
    }
    if persisted_state_ids and (
        None in (state_id, policy_state_id, allocation_state_id)
        or len(persisted_state_ids) != 1
    ):
        blockers.append(
            _message(
                "STATE_CHAIN_MISMATCH",
                "A cadeia congelada aponta para snapshots financeiros divergentes.",
                fields=("financial_state_snapshot_id",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    policy_id = policy.get("policy_id")
    allocation_policy_id = allocation.get("financial_policy_id")
    if (policy_id is None) != (allocation_policy_id is None) or (
        policy_id is not None and policy_id != allocation_policy_id
    ):
        blockers.append(
            _message(
                "POLICY_CHAIN_MISMATCH",
                "A Allocation não referencia a Financial Policy informada.",
                fields=("financial_policy_decision_id",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    policy_digest = policy.get("decision_fingerprint")
    if policy_digest and policy_fingerprint_from_payload(policy) != policy_digest:
        blockers.append(
            _message(
                "POLICY_FINGERPRINT_INVALID",
                "O fingerprint da Financial Policy não confere.",
                fields=("financial_policy.decision_fingerprint",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    allocation_digest = allocation.get("decision_fingerprint")
    if allocation_digest and allocation_fingerprint_from_payload(allocation) != allocation_digest:
        blockers.append(
            _message(
                "ALLOCATION_FINGERPRINT_INVALID",
                "O fingerprint da Capital Allocation não confere.",
                fields=("capital_allocation.decision_fingerprint",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    allocation_state_digest = allocation.get("input_fingerprint")
    expected_state_digest = _sha256(_semantic(state, "snapshot_id"))
    if allocation_state_digest != expected_state_digest:
        blockers.append(
            _message(
                "STATE_ALLOCATION_INPUT_MISMATCH",
                "A Allocation não foi produzida a partir deste Financial State.",
                fields=("capital_allocation.input_fingerprint",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    if allocation.get("policy_fingerprint") and policy_digest != allocation.get(
        "policy_fingerprint"
    ):
        blockers.append(
            _message(
                "POLICY_ALLOCATION_FINGERPRINT_MISMATCH",
                "A Allocation não foi produzida a partir desta Policy.",
                fields=("capital_allocation.policy_fingerprint",),
                rule_ids=("IOV1-CHAIN-001",),
            )
        )
    return blockers


def _profile_gate(profile_context: Mapping[str, Any]) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    status = str(profile_context.get("status") or "MISSING").upper()
    profile = profile_context.get("effective_profile")
    normalized = str(profile).upper() if profile is not None else None
    if status in {"MISSING", "INCONSISTENT"} or normalized not in PROFILE_ORDER:
        blockers.append(
            _message(
                "INVESTOR_PROFILE_REQUIRED",
                "Informe um perfil de investidor válido para avaliar oportunidades.",
                fields=("financial_profiles.risk_profile",),
                rule_ids=("IOV1-PROFILE-001",),
            )
        )
        return None, blockers, warnings
    if status == "MIXED":
        warnings.append(
            _message(
                "HOUSEHOLD_PROFILES_DIFFER",
                "Os membros possuem perfis distintos; foi aplicado o perfil mais conservador.",
                fields=("profile_context.members",),
                rule_ids=("IOV1-PROFILE-001",),
            )
        )
    return normalized, blockers, warnings


def _risk_compatible(profile: str, risk: str) -> bool:
    normalized = risk.upper()
    if profile == "CONSERVATIVE":
        return normalized == "LOW"
    if profile == "MODERATE":
        return normalized in {"LOW", "MEDIUM"}
    return normalized in {"LOW", "MEDIUM", "HIGH"}


def _concentrated_markets(portfolio_context: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for row in portfolio_context.get("concentration") or []:
        percentage = _decimal(row.get("percentage"))
        market = str(row.get("market") or "").upper()
        if market and percentage is not None and percentage > CONCENTRATION_THRESHOLD_PCT:
            result.add(market)
    return result


def _candidate_action(candidate: Mapping[str, Any], profile: str) -> tuple[str, str]:
    guardrail = str(candidate.get("guardrail_status") or "UNKNOWN").upper()
    if guardrail == "BLOCKED":
        return "AVOID", "O guardrail canônico bloqueou esta oportunidade."
    if guardrail == "WARNING":
        return "WAIT", "O guardrail exige cautela; nenhum capital foi comprometido."
    if guardrail != "APPROVED":
        return "NO_RECOMMENDATION", "O guardrail não está disponível ou não é reconhecido."
    if str(candidate.get("freshness_status") or "UNKNOWN").upper() != "FRESH":
        return "WAIT", "Os dados de mercado não estão suficientemente atuais."
    if candidate.get("price_reference") is None:
        return "NO_RECOMMENDATION", "Preço de referência ausente."
    if candidate.get("recommendation_score") is None:
        return "NO_RECOMMENDATION", "Score de recomendação ausente."
    if candidate.get("liquidity_score") is None:
        return "WAIT", "Liquidez não conhecida; nenhum capital foi comprometido."
    if not _risk_compatible(profile, str(candidate.get("risk_level") or "UNKNOWN")):
        return "AVOID", "O risco conhecido não é compatível com o perfil atual."
    return "BUY", "Oportunidade aprovada, atual e compatível com o perfil."


def _class_plan(
    *,
    budget: Decimal,
    candidates: Sequence[Mapping[str, Any]],
    profile: str,
    concentrated_markets: set[str],
    market_context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    by_market: dict[str, list[dict[str, Any]]] = {market: [] for market in SUPPORTED_MARKETS}
    for raw in candidates:
        candidate = deepcopy(dict(raw))
        market = str(candidate.get("market") or candidate.get("asset_class") or "").upper()
        if market not in by_market:
            continue
        action, reason = _candidate_action(candidate, profile)
        candidate["asset_class"] = market
        candidate["market"] = market
        candidate["action"] = action
        candidate["reason"] = reason
        candidate["capital_committed"] = Decimal("0.00")
        candidate["quantity_suggested"] = 0
        by_market[market].append(candidate)

    market_rows = {
        str(row.get("market") or "").upper(): row
        for row in market_context.get("markets") or []
    }
    eligible_scores: dict[str, Decimal] = {}
    for market in SUPPORTED_MARKETS:
        rows = by_market[market]
        buys = [row for row in rows if row["action"] == "BUY"]
        market_row = market_rows.get(market, {})
        freshness = str(market_row.get("freshness_status") or "UNKNOWN").upper()
        if market in concentrated_markets:
            eligibility = "INELIGIBLE"
            reason = "A carteira conhecida já excede o limite de concentração desta classe."
        elif freshness == "STALE":
            eligibility = "INELIGIBLE"
            reason = "Os dados desta classe estão stale."
        elif not rows and market_row.get("status") in {"UNAVAILABLE", "UNKNOWN", None}:
            eligibility = "UNKNOWN"
            reason = "Não há dados suficientes para avaliar esta classe."
        elif not buys:
            eligibility = "LIMITED"
            reason = "Nenhuma oportunidade desta classe passou por todos os critérios."
        else:
            eligibility = "ELIGIBLE"
            reason = "Há oportunidade aprovada, atual e compatível com o perfil."
            score = max(
                value
                for value in (_decimal(row.get("recommendation_score")) for row in buys)
                if value is not None
            )
            if score > 0:
                eligible_scores[market] = score
        decisions.append(
            {
                "asset_class": market,
                "market": market,
                "eligibility": eligibility,
                "reason": reason,
                "risk_fit": "COMPATIBLE" if buys else "UNKNOWN",
                "liquidity_fit": (
                    "KNOWN_BY_SCORE"
                    if rows and all(row.get("liquidity_score") is not None for row in rows)
                    else "UNKNOWN"
                ),
                "data_quality": freshness,
                "constraints": [
                    "PORTFOLIO_CONCENTRATION"
                    if market in concentrated_markets
                    else "STRICT_GUARDRAIL"
                ],
                "opportunity_count": len(rows),
                "eligible_opportunity_count": len(buys),
            }
        )

    for asset_class in UNSUPPORTED_CLASSES:
        decisions.append(
            {
                "asset_class": asset_class,
                "market": None,
                "eligibility": "UNKNOWN",
                "reason": "A infraestrutura atual não avalia esta classe com o pipeline completo v1.",
                "risk_fit": "UNKNOWN",
                "liquidity_fit": "UNKNOWN",
                "data_quality": "UNSUPPORTED",
                "constraints": ["PIPELINE_NOT_SUPPORTED"],
                "opportunity_count": 0,
                "eligible_opportunity_count": 0,
            }
        )

    class_allocations: list[dict[str, Any]] = []
    if eligible_scores and budget > 0:
        score_total = sum(eligible_scores.values(), Decimal("0"))
        assigned = Decimal("0.00")
        ordered = sorted(eligible_scores, key=lambda key: (-eligible_scores[key], key))
        for index, market in enumerate(ordered):
            if index == len(ordered) - 1:
                amount = budget - assigned
            else:
                amount = _money(budget * eligible_scores[market] / score_total)
                assert amount is not None
                assigned += amount
            class_allocations.append(
                {
                    "asset_class": market,
                    "market": market,
                    "signal_score": eligible_scores[market],
                    "allocated_amount": amount,
                    "suggested_capital": Decimal("0.00"),
                    "remaining_cash": amount,
                    "method": "RELATIVE_CANONICAL_RECOMMENDATION_SCORE",
                }
            )

    allocation_by_market = {row["market"]: row for row in class_allocations}
    ranked: list[dict[str, Any]] = []
    for market in SUPPORTED_MARKETS:
        rows = sorted(
            by_market[market],
            key=lambda row: (
                0 if row["action"] == "BUY" else 1,
                -(_decimal(row.get("recommendation_score")) or Decimal("-1")),
                str(row.get("ticker") or row.get("symbol") or ""),
            ),
        )
        class_allocation = allocation_by_market.get(market)
        committed = False
        for row in rows:
            if row["action"] == "BUY" and class_allocation is not None and not committed:
                price = _money(row.get("price_reference"), allow_none=True)
                class_budget = class_allocation["allocated_amount"]
                if price is not None and price > 0 and class_budget >= price:
                    advisor_quantity = int(row.get("quantity_candidate") or 0)
                    max_quantity = int(class_budget // price)
                    quantity = min(advisor_quantity, max_quantity)
                    if quantity > 0:
                        capital = _money(price * quantity)
                        assert capital is not None
                        row["quantity_suggested"] = quantity
                        row["capital_committed"] = capital
                        class_allocation["suggested_capital"] = capital
                        class_allocation["remaining_cash"] = class_budget - capital
                        committed = True
                    else:
                        row["action"] = "WAIT"
                        row["reason"] = "O orçamento da classe não comporta a quantidade mínima conhecida."
                else:
                    row["action"] = "WAIT"
                    row["reason"] = "O orçamento da classe não comporta uma unidade pelo preço conhecido."
            elif row["action"] == "BUY":
                row["action"] = "WAIT"
                row["reason"] = "Mantida como alternativa; o mesmo capital não pode ser comprometido duas vezes."
            ranked.append(row)

    action_order = {"BUY": 0, "WAIT": 1, "AVOID": 2, "NO_RECOMMENDATION": 3}
    ranked.sort(
        key=lambda row: (
            action_order.get(str(row.get("action")), 4),
            -(_decimal(row.get("recommendation_score")) or Decimal("-1")),
            str(row.get("market") or ""),
            str(row.get("ticker") or row.get("symbol") or ""),
        )
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank

    return decisions, class_allocations, ranked


def calculate_investment_orchestration(
    financial_state: Mapping[str, Any],
    financial_policy: Mapping[str, Any],
    capital_allocation: Mapping[str, Any],
    *,
    profile_context: Mapping[str, Any],
    portfolio_context: Mapping[str, Any],
    market_context: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Transform an authorized investment bucket into a safe, auditable strategy."""

    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    state = deepcopy(dict(financial_state))
    policy = deepcopy(dict(financial_policy))
    allocation = deepcopy(dict(capital_allocation))
    profile_data = deepcopy(dict(profile_context))
    portfolio_data = deepcopy(dict(portfolio_context))
    market_data = deepcopy(dict(market_context))

    blockers = _validate_chain(state, policy, allocation)
    warnings: list[dict[str, Any]] = []
    missing_information: list[dict[str, Any]] = []
    raw_budget = allocation.get("investment_bucket_amount")
    if raw_budget is None:
        budget = Decimal("0.00")
        blockers.append(
            _message(
                "INVESTMENT_BUDGET_UNKNOWN",
                "O investment bucket está ausente; nenhuma alocação foi presumida.",
                fields=("capital_allocation.investment_bucket_amount",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    else:
        budget_value = _money(raw_budget)
        assert budget_value is not None
        budget = budget_value
        if budget < 0:
            blockers.append(
                _message(
                    "INVESTMENT_BUDGET_INVALID",
                    "O investment bucket não pode ser negativo.",
                    fields=("capital_allocation.investment_bucket_amount",),
                    rule_ids=("IOV1-GATE-001",),
                )
            )
            budget = Decimal("0.00")

    currency = str(allocation.get("currency") or "").upper()
    if currency != SETTLEMENT_CURRENCY:
        blockers.append(
            _message(
                "CURRENCY_CONVERSION_MISSING",
                "A moeda não pode ser comparada sem uma conversão FX confiável.",
                fields=("capital_allocation.currency",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    readiness = str(policy.get("investment_readiness") or "BLOCKED").upper()
    allocation_status = str(
        allocation.get("allocation_status") or "BLOCKED"
    ).upper()
    if readiness == "BLOCKED" or allocation_status == "BLOCKED":
        blockers.append(
            _message(
                "INVESTMENT_READINESS_BLOCKED",
                "A cadeia financeira não autoriza novos investimentos.",
                fields=("financial_policy.investment_readiness",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    elif readiness not in {"LIMITED", "READY"}:
        blockers.append(
            _message(
                "INVESTMENT_READINESS_INVALID",
                "A prontidão financeira não usa um estado canônico compatível.",
                fields=("financial_policy.investment_readiness",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    elif allocation_status not in {"CONSTRAINED", "ACTIVE", "SURPLUS"}:
        blockers.append(
            _message(
                "ALLOCATION_STATUS_INVALID",
                "A Capital Allocation não usa um estado canônico compatível.",
                fields=("capital_allocation.allocation_status",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    elif readiness == "LIMITED":
        warnings.append(
            _message(
                "INVESTMENT_READINESS_LIMITED",
                "A prontidão financeira é limitada; apenas capital residual pode ser avaliado.",
                fields=("financial_policy.investment_readiness",),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    if budget == 0:
        blockers.append(
            _message(
                "NO_AUTHORIZED_INVESTMENT_CAPITAL",
                "Não há capital comprovadamente liberado para novos investimentos.",
                fields=("capital_allocation.investment_bucket_amount",),
                rule_ids=("IOV1-GATE-001",),
            )
        )

    state_quality = str(state.get("data_quality") or "INSUFFICIENT").upper()
    try:
        state_confidence = int(state.get("confidence"))
    except (TypeError, ValueError):
        state_confidence = None
    allocation_gate_status = str(
        (allocation.get("data_gate") or {}).get("status") or "BLOCKED"
    ).upper()
    if (
        state_quality not in {"COMPLETE", "PARTIAL", "STALE"}
        or state_confidence is None
        or not 0 <= state_confidence <= 100
        or allocation_gate_status not in {"PASS", "LIMITED"}
    ):
        blockers.append(
            _message(
                "FINANCIAL_DATA_GATE_BLOCKED",
                "A qualidade ou a confiança da cadeia financeira não permite avaliar investimentos com segurança.",
                fields=(
                    "financial_state.data_quality",
                    "financial_state.confidence",
                    "capital_allocation.data_gate.status",
                ),
                rule_ids=("IOV1-GATE-001",),
            )
        )
    elif state_quality in {"PARTIAL", "STALE"}:
        warnings.append(
            _message(
                "FINANCIAL_DATA_LIMITED",
                "A estratégia usa somente os dados financeiros conhecidos; informações parciais ou antigas podem alterá-la.",
                fields=tuple(
                    [
                        *[str(item) for item in state.get("missing_fields") or []],
                        *[str(item) for item in state.get("stale_fields") or []],
                    ]
                ),
                rule_ids=("IOV1-GATE-001",),
            )
        )

    profile, profile_blockers, profile_warnings = _profile_gate(profile_data)
    if budget > 0:
        blockers.extend(profile_blockers)
        warnings.extend(profile_warnings)
        if profile_data.get("investment_horizon") in {None, ""}:
            warnings.append(
                _message(
                    "INVESTMENT_HORIZON_UNKNOWN",
                    "O horizonte de investimento não está disponível no perfil canônico; a estratégia permanece limitada.",
                    fields=("profile_context.investment_horizon",),
                    rule_ids=("IOV1-PROFILE-001", "IOV1-CLASS-001"),
                )
            )
            missing_information.append(
                _message(
                    "INVESTMENT_HORIZON_REQUIRED",
                    "Informar o horizonte permitiria avaliar melhor compatibilidade de liquidez e risco.",
                    fields=("financial_profiles.investment_horizon",),
                    rule_ids=("IOV1-PROFILE-001", "IOV1-CLASS-001"),
                )
            )

    portfolio_status = str(portfolio_data.get("status") or "UNKNOWN").upper()
    if portfolio_status == "UNKNOWN":
        warnings.append(
            _message(
                "PORTFOLIO_UNKNOWN",
                "A carteira real não foi presumida como vazia; análise de concentração está limitada.",
                fields=("owned_assets",),
                rule_ids=("IOV1-PORTFOLIO-001",),
            )
        )
        missing_information.append(
            _message(
                "PORTFOLIO_DATA_REQUIRED",
                "Cadastre posições reais para avaliar concentração e duplicidade de exposição.",
                fields=("owned_assets",),
                rule_ids=("IOV1-PORTFOLIO-001",),
            )
        )
    elif portfolio_status in {"PARTIAL", "INCONSISTENT"}:
        warnings.append(
            _message(
                "PORTFOLIO_PARTIAL",
                "A carteira conhecida possui dados incompletos; a estratégia permanece limitada.",
                fields=tuple(str(item) for item in portfolio_data.get("missing_information") or []),
                rule_ids=("IOV1-PORTFOLIO-001",),
            )
        )

    market_status = str(market_data.get("status") or "UNAVAILABLE").upper()
    if budget > 0 and profile is not None and market_status in {
        "UNAVAILABLE",
        "BLOCKED",
        "NOT_CONSULTED",
    }:
        blockers.append(
            _message(
                "MARKET_CONTEXT_UNAVAILABLE",
                "Nenhuma classe possui contexto de mercado confiável para esta decisão.",
                fields=("market_context",),
                rule_ids=("IOV1-MARKET-001",),
            )
        )
    for failure in market_data.get("partial_failures") or []:
        warnings.append(
            _message(
                "MARKET_CLASS_UNAVAILABLE",
                f"A classe {failure.get('market') or 'desconhecida'} não pôde ser avaliada.",
                fields=(f"market.{failure.get('market') or 'unknown'}",),
                rule_ids=("IOV1-MARKET-001",),
            )
        )
    for field in market_data.get("missing_information") or []:
        missing_information.append(
            _message(
                "MARKET_DATA_MISSING",
                "Dados de score e guardrail alinhados estão ausentes para uma classe.",
                fields=(str(field),),
                rule_ids=("IOV1-MARKET-001",),
            )
        )

    candidates = [
        item
        for item in (market_data.get("candidates") or [])
        if isinstance(item, Mapping)
    ]
    class_decisions: list[dict[str, Any]] = []
    class_allocations: list[dict[str, Any]] = []
    ranked_opportunities: list[dict[str, Any]] = []
    if not blockers and profile is not None:
        class_decisions, class_allocations, ranked_opportunities = _class_plan(
            budget=budget,
            candidates=candidates,
            profile=profile,
            concentrated_markets=_concentrated_markets(portfolio_data),
            market_context=market_data,
        )
    else:
        for raw in candidates:
            candidate = deepcopy(dict(raw))
            guardrail = str(candidate.get("guardrail_status") or "UNKNOWN").upper()
            candidate["action"] = "AVOID" if guardrail == "BLOCKED" else "NO_RECOMMENDATION"
            candidate["quantity_suggested"] = 0
            candidate["capital_committed"] = Decimal("0.00")
            ranked_opportunities.append(candidate)

    suggested = sum(
        (Decimal(str(row.get("capital_committed") or "0")) for row in ranked_opportunities),
        Decimal("0.00"),
    ).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
    if suggested < 0 or suggested > budget:
        raise AssertionError("suggested capital violated investment budget conservation")
    remaining = (budget - suggested).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
    class_allocated = sum(
        (Decimal(str(row.get("allocated_amount") or "0")) for row in class_allocations),
        Decimal("0.00"),
    )
    if class_allocated > budget or remaining < 0:
        raise AssertionError("class allocation violated capital conservation")
    if any(
        Decimal(str(row.get("suggested_capital") or "0"))
        > Decimal(str(row.get("allocated_amount") or "0"))
        for row in class_allocations
    ):
        raise AssertionError("candidate commitment exceeded its class allocation")

    if blockers:
        status = "BLOCKED"
    elif suggested == 0:
        status = "NO_SUITABLE_OPPORTUNITY"
    elif warnings or readiness == "LIMITED":
        status = "LIMITED"
    else:
        status = "ACTIVE"

    state_fingerprint = _sha256(_semantic(state, "snapshot_id"))
    policy_fingerprint = str(policy.get("decision_fingerprint") or _sha256(policy))
    allocation_fingerprint = str(
        allocation.get("decision_fingerprint") or _sha256(allocation)
    )
    market_context_fingerprint = _sha256(market_data)
    ruleset_fingerprint = _ruleset_fingerprint()
    evidence = [
        {
            "code": "AUTHORIZED_INVESTMENT_BUDGET",
            "label": "Capital máximo autorizado",
            "value": budget,
            "unit": currency or SETTLEMENT_CURRENCY,
            "source": "capital_allocation.investment_bucket_amount",
        },
        {
            "code": "INVESTOR_PROFILE",
            "label": "Perfil efetivo conhecido",
            "value": profile,
            "unit": "PROFILE",
            "source": "profile_context.effective_profile",
        },
        {
            "code": "SUGGESTED_CAPITAL",
            "label": "Capital sugerido nas oportunidades aprovadas",
            "value": suggested,
            "unit": currency or SETTLEMENT_CURRENCY,
            "source": "ranked_opportunities.capital_committed",
        },
        {
            "code": "REMAINING_INVESTMENT_CASH",
            "label": "Capital preservado em caixa",
            "value": remaining,
            "unit": currency or SETTLEMENT_CURRENCY,
            "source": "investment_orchestrator.conservation",
        },
    ]
    rule_traces = [
        _trace(
            "IOV1-CHAIN-001",
            "TRIGGERED" if any(item["code"].endswith("MISMATCH") or "FINGERPRINT" in item["code"] for item in blockers) else "NOT_TRIGGERED",
            {"blocker_count": len(blockers)},
            "A cadeia foi validada antes de qualquer consulta financiável.",
        ),
        _trace(
            "IOV1-GATE-001",
            "TRIGGERED" if budget > 0 and readiness in {"LIMITED", "READY"} else "NOT_TRIGGERED",
            {"investment_budget": budget, "investment_readiness": readiness},
            "Somente o bucket autorizado pelo Autopilot 3 foi considerado.",
        ),
        _trace(
            "IOV1-PROFILE-001",
            "TRIGGERED" if profile is None or profile_data.get("status") == "MIXED" else "NOT_TRIGGERED",
            {
                "profile_status": profile_data.get("status"),
                "effective_profile": profile,
                "investment_horizon": profile_data.get("investment_horizon"),
            },
            "O perfil foi consumido sem default implícito e o horizonte ausente permaneceu explícito.",
        ),
        _trace(
            "IOV1-PORTFOLIO-001",
            "TRIGGERED" if portfolio_status != "COMPLETE" or bool(_concentrated_markets(portfolio_data)) else "NOT_TRIGGERED",
            {
                "portfolio_status": portfolio_status,
                "concentrated_markets": sorted(_concentrated_markets(portfolio_data)),
            },
            "A carteira conhecida limitou concentração; ausência não foi tratada como carteira vazia.",
        ),
        _trace(
            "IOV1-MARKET-001",
            "TRIGGERED" if market_status not in {"AVAILABLE"} or bool(market_data.get("partial_failures")) else "NOT_TRIGGERED",
            {
                "market_status": market_status,
                "partial_failures": market_data.get("partial_failures") or [],
            },
            "Somente snapshots atuais com score, preço e guardrail alinhados foram avaliados.",
        ),
        _trace(
            "IOV1-CLASS-001",
            "TRIGGERED" if class_decisions else "NOT_EVALUATED",
            {"class_eligibility": {item["asset_class"]: item["eligibility"] for item in class_decisions}},
            "A elegibilidade de cada classe deriva do contexto disponível e das restrições conhecidas.",
        ),
        _trace(
            "IOV1-ALLOCATE-001",
            "TRIGGERED" if class_allocations else "NOT_EVALUATED",
            {"class_allocated_total": class_allocated},
            "A distribuição por classe usou a força relativa dos scores canônicos, sem pesos universais.",
        ),
        _trace(
            "IOV1-GUARDRAIL-001",
            "TRIGGERED" if ranked_opportunities else "NOT_TRIGGERED",
            {"actions": [item.get("action") for item in ranked_opportunities]},
            "Guardrails prevaleceram sobre scores e orçamento.",
        ),
        _trace(
            "IOV1-BUDGET-001",
            "TRIGGERED" if ranked_opportunities else "NOT_EVALUATED",
            {
                "opportunity_count": len(ranked_opportunities),
                "committed_count": sum(1 for item in ranked_opportunities if item.get("capital_committed")),
            },
            "Budget Advisor forneceu possibilidades; o Orchestrator reconciliou compromissos sem gasto duplo.",
        ),
        _trace(
            "IOV1-NOOP-001",
            "TRIGGERED" if not blockers and suggested == 0 else "NOT_TRIGGERED",
            {"suggested_capital": suggested, "remaining": remaining},
            "Ausência de oportunidade adequada preserva o capital em caixa.",
        ),
        _trace(
            "IOV1-CONSERVE-001",
            "NOT_TRIGGERED",
            {"investment_budget": budget, "suggested_capital": suggested, "remaining": remaining},
            "O capital sugerido mais a sobra reconcilia o budget autorizado.",
        ),
        _trace(
            "IOV1-ROUND-001",
            "TRIGGERED",
            {"money_quantum": MONEY_QUANTUM, "rounding": str(MONEY_ROUNDING)},
            "Valores monetários foram reconciliados em Decimal com arredondamento determinístico.",
        ),
        _trace(
            "IOV1-TRADING-001",
            "NOT_TRIGGERED",
            {"speculative_capital": Decimal("0.00"), "trading_dispatch": False},
            "Nenhum capital ou comando foi enviado ao Trading V2.",
        ),
    ]

    result: dict[str, Any] = {
        "orchestration_id": None,
        "household_id": state.get("household_id"),
        "financial_state_snapshot_id": state.get("snapshot_id"),
        "financial_policy_decision_id": policy.get("policy_id"),
        "capital_allocation_decision_id": allocation.get("allocation_id"),
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "status": status,
        "currency": currency or SETTLEMENT_CURRENCY,
        "investment_budget": budget,
        "profile_context": profile_data,
        "portfolio_context": portfolio_data,
        "market_context": market_data,
        "asset_class_decisions": class_decisions,
        "class_allocations": class_allocations,
        "ranked_opportunities": ranked_opportunities,
        "suggested_capital": suggested,
        "remaining_investment_cash": remaining,
        "speculative_capital": Decimal("0.00"),
        "trading_dispatch": False,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "missing_information": _dedupe(missing_information),
        "evidence": evidence,
        "rule_traces": rule_traces,
        "state_fingerprint": state_fingerprint,
        "policy_fingerprint": policy_fingerprint,
        "allocation_fingerprint": allocation_fingerprint,
        "market_context_fingerprint": market_context_fingerprint,
        "ruleset_fingerprint": ruleset_fingerprint,
        "decision_fingerprint": "",
        "generated_at": generated,
        "created_at": None,
    }
    result["decision_fingerprint"] = decision_fingerprint_from_payload(result)
    return result

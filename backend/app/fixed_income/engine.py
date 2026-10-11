from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from backend.app.fixed_income.rules import (
    DURATION_SENSITIVE_TYPES,
    ENGINE_VERSION,
    FRESHNESS_DAYS,
    LIQUID_TYPES,
    MONEY_QUANTUM,
    MONEY_ROUNDING,
    RULES_VERSION,
    SETTLEMENT_CURRENCY,
)
from backend.app.fixed_income.schemas import FixedIncomeEvaluation
from backend.app.intelligence.services.budget_advisor_service import (
    build_amount_budget_candidate,
)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _money(value: Any) -> Decimal | None:
    parsed = _decimal(value)
    if parsed is None:
        return None
    return parsed.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


def _first_known(*values: Any) -> Any:
    """Return the first non-None value without turning real zero into absence."""

    return next((value for value in values if value is not None), None)


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _message(code: str, message: str, *fields: str) -> dict[str, Any]:
    return {"code": code, "message": message, "fields": list(fields)}


def _trace(
    rule_id: str,
    outcome: str,
    observed: Mapping[str, Any],
    explanation: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_version": RULES_VERSION,
        "outcome": outcome,
        "observed_values": dict(observed),
        "explanation": explanation,
    }


def _risk_level(product_type: str) -> str:
    return "LOW" if product_type == "TREASURY_SELIC" else "MEDIUM"


def evaluate_fixed_income_product(
    product: Mapping[str, Any],
    *,
    investment_budget: Decimal,
    profile: str,
    investment_horizon_months: int | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Evaluate known product facts without predicting or executing returns."""

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    budget = _money(investment_budget)
    if budget is None or budget < 0:
        raise ValueError("investment_budget must be a finite non-negative amount")

    product_id = product.get("id")
    source_product_id = str(product.get("source_product_id") or "").strip()
    name = str(product.get("nome") or product.get("name") or "").strip()
    product_type = str(product.get("tipo") or product.get("product_type") or "").upper()
    currency = str(product.get("currency") or "").upper()
    indexer = str(product.get("indexador") or product.get("indexer") or "").upper()
    market_date = _date(product.get("market_date"))
    maturity = _date(product.get("vencimento") or product.get("maturity_date"))
    unit_price = _money(product.get("unit_price"))
    minimum = _money(
        _first_known(
            product.get("investimento_minimo"),
            product.get("minimum_investment"),
        )
    )
    liquidity_type = str(product.get("liquidity_type") or "").upper()
    active = product.get("is_active") is True
    purchase_rate = _decimal(
        _first_known(product.get("purchase_rate"), product.get("taxa_juros"))
    )
    profile_value = str(profile or "").upper()

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    reasons: list[str] = []
    traces: list[dict[str, Any]] = []

    critical_missing = [
        field
        for field, value in (
            ("source_product_id", source_product_id),
            ("name", name),
            ("product_type", product_type),
            ("currency", currency),
            ("market_date", market_date),
            ("maturity_date", maturity),
            ("unit_price", unit_price),
            ("minimum_investment", minimum),
            ("indexer", indexer),
            ("purchase_rate", purchase_rate),
        )
        if value in (None, "")
    ]
    if critical_missing:
        blockers.append(
            _message(
                "MISSING_CRITICAL_PRODUCT_DATA",
                "O produto não possui todos os fatos necessários para uma avaliação segura.",
                *critical_missing,
            )
        )
    if not active:
        blockers.append(_message("INACTIVE_PRODUCT", "O produto não está ativo.", "is_active"))
    if maturity is not None and maturity <= as_of.date():
        blockers.append(_message("EXPIRED_PRODUCT", "O produto já venceu.", "maturity_date"))
    if currency and currency != SETTLEMENT_CURRENCY:
        blockers.append(
            _message(
                "CURRENCY_MISMATCH",
                "A moeda exige conversão FX que não está disponível.",
                "currency",
            )
        )

    age_days = (as_of.date() - market_date).days if market_date is not None else None
    freshness = (
        "FRESH"
        if age_days is not None and 0 <= age_days <= FRESHNESS_DAYS
        else "STALE" if age_days is not None else "UNKNOWN"
    )
    if age_days is not None and age_days < 0:
        blockers.append(
            _message("FUTURE_MARKET_DATE", "A data de mercado está no futuro.", "market_date")
        )
    elif freshness == "STALE":
        warnings.append(
            _message("STALE_PRODUCT", "Os dados do produto estão desatualizados.", "market_date")
        )

    if minimum is not None and minimum > budget:
        warnings.append(
            _message(
                "MINIMUM_INVESTMENT_EXCEEDS_BUDGET",
                "O orçamento autorizado não comporta o aporte mínimo conhecido.",
                "minimum_investment",
                "investment_budget",
            )
        )

    if budget == 0:
        blockers.append(
            _message(
                "NO_AUTHORIZED_INVESTMENT_BUDGET",
                "Não existe capital autorizado para financiar este produto.",
                "investment_budget",
            )
        )

    liquid = liquidity_type in LIQUID_TYPES
    maturity_fit = "UNKNOWN"
    if investment_horizon_months is None:
        if product_type in DURATION_SENSITIVE_TYPES:
            warnings.append(
                _message(
                    "INVESTMENT_HORIZON_UNKNOWN",
                    "O horizonte é necessário para avaliar este vencimento com segurança.",
                    "investment_horizon_months",
                )
            )
        maturity_fit = "UNKNOWN_LIQUID" if liquid else "UNKNOWN"
    elif investment_horizon_months <= 0:
        blockers.append(
            _message(
                "INVALID_INVESTMENT_HORIZON",
                "O horizonte informado deve ser positivo.",
                "investment_horizon_months",
            )
        )
    elif maturity is not None:
        horizon_date = as_of.date() + timedelta(days=investment_horizon_months * 30)
        if maturity > horizon_date and product_type in DURATION_SENSITIVE_TYPES:
            warnings.append(
                _message(
                    "MATURITY_EXCEEDS_KNOWN_HORIZON",
                    "O vencimento supera o horizonte conhecido e a liquidez não é comprovada.",
                    "maturity_date",
                    "investment_horizon_months",
                )
            )
            maturity_fit = "INCOMPATIBLE"
        elif maturity > horizon_date:
            maturity_fit = "LIQUID_BEFORE_MATURITY"
        else:
            maturity_fit = "COMPATIBLE"

    if not liquidity_type:
        warnings.append(
            _message(
                "LIQUIDITY_UNKNOWN",
                "A liquidez não é conhecida; nenhum prazo foi presumido.",
                "liquidity_type",
            )
        )

    risk = _risk_level(product_type)
    compatible = (
        risk == "LOW"
        or (profile_value == "MODERATE" and risk in {"LOW", "MEDIUM"})
        or (profile_value == "AGGRESSIVE" and risk in {"LOW", "MEDIUM", "HIGH"})
    )
    if profile_value not in {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}:
        blockers.append(
            _message("PROFILE_MISSING", "O perfil de investidor não é válido.", "risk_profile")
        )
    elif not compatible:
        warnings.append(
            _message(
                "PROFILE_MISMATCH",
                "O risco de mercado conhecido não é compatível com o perfil atual.",
                "risk_profile",
            )
        )

    if blockers:
        guardrail = "BLOCKED"
        action = "AVOID"
        eligibility = "INELIGIBLE"
    elif warnings:
        guardrail = "WARNING"
        action = "WAIT"
        eligibility = "LIMITED"
    else:
        guardrail = "APPROVED"
        action = "BUY"
        eligibility = "ELIGIBLE"

    # Suitability score intentionally excludes nominal rate. It is only a
    # deterministic ranking signal for known fit and data quality.
    score = Decimal("70")
    if freshness == "FRESH":
        score += Decimal("10")
    if liquid:
        score += Decimal("10")
    if maturity_fit in {"COMPATIBLE", "LIQUID_BEFORE_MATURITY", "UNKNOWN_LIQUID"}:
        score += Decimal("10")
    if guardrail == "BLOCKED":
        score = Decimal("0")
    elif guardrail == "WARNING":
        score = min(score, Decimal("69"))

    budget_candidate = build_amount_budget_candidate(
        budget=budget,
        minimum_investment=minimum,
    )
    candidate_amount = (
        budget_candidate.candidate_amount if action == "BUY" else Decimal("0.00")
    )
    data_timestamp = (
        datetime.combine(market_date, time.min, tzinfo=timezone.utc)
        if market_date is not None
        else None
    )
    reasons.append(
        "A adequação considera dados, liquidez, vencimento, risco, perfil e orçamento; a taxa nominal não define o ranking."
    )
    traces.extend(
        [
            _trace(
                "FIV1-DATA-001",
                "TRIGGERED" if blockers else "NOT_TRIGGERED",
                {"freshness": freshness, "active": active, "missing": critical_missing},
                "Dados críticos e freshness foram avaliados.",
            ),
            _trace(
                "FIV1-BUDGET-001",
                "TRIGGERED" if minimum is not None and minimum > budget else "NOT_TRIGGERED",
                {"minimum_investment": minimum, "investment_budget": budget},
                "O aporte mínimo foi comparado somente quando conhecido.",
            ),
            _trace(
                "FIV1-HORIZON-001",
                "TRIGGERED" if any(item["code"].startswith(("MATURITY", "INVESTMENT_HORIZON")) for item in warnings) else "NOT_TRIGGERED",
                {
                    "maturity_date": maturity,
                    "investment_horizon_months": investment_horizon_months,
                    "liquidity_type": liquidity_type or None,
                },
                "Horizonte ausente permaneceu desconhecido.",
            ),
        ]
    )

    result = {
        "product_id": product_id,
        "source_product_id": source_product_id,
        "product_name": name or "Produto de renda fixa",
        "product_type": product_type or "UNKNOWN",
        "asset_id": product.get("asset_catalog_id"),
        "asset_name": name or None,
        "symbol": name or source_product_id or "Renda fixa",
        "ticker": product.get("catalog_ticker"),
        "asset_class": "FIXED_INCOME",
        "market": "FIXED_INCOME",
        "eligibility": eligibility,
        "action": action,
        "guardrail_status": guardrail,
        "suitability": "COMPATIBLE" if compatible else "INCOMPATIBLE",
        "liquidity_assessment": "KNOWN_LIQUID" if liquid else "UNKNOWN",
        "maturity_fit": maturity_fit,
        "risk_assessment": risk,
        "risk_level": risk,
        "recommendation_score": score,
        "liquidity_score": Decimal("100") if liquid else None,
        "minimum_investment": minimum,
        "candidate_amount": candidate_amount,
        "purchase_mode": "AMOUNT",
        "price_reference": unit_price,
        "quantity_candidate": 0,
        "capital_required": minimum or Decimal("0.00"),
        "indexer": indexer or None,
        "reference_rate": purchase_rate,
        "purchase_rate": purchase_rate,
        "redemption_rate": _decimal(product.get("redemption_rate")),
        "maturity_date": maturity,
        "liquidity_type": liquidity_type or None,
        "liquidity_days": product.get("liquidez_dias"),
        "guarantee_type": product.get("guarantee_type"),
        "tax_treatment": product.get("tax_treatment"),
        "currency": currency or None,
        "source": product.get("source"),
        "market_date": market_date,
        "data_timestamp": data_timestamp,
        "freshness_status": freshness,
        "price_source": product.get("source"),
        "confidence": Decimal("90") if guardrail == "APPROVED" else Decimal("60") if guardrail == "WARNING" else Decimal("0"),
        "warnings": warnings,
        "blockers": blockers,
        "reasons": reasons,
        "evidence": [
            {"code": "PRODUCT_TYPE", "value": product_type or None},
            {"code": "INDEXER", "value": indexer or None},
            {"code": "MATURITY", "value": maturity},
            {"code": "LIQUIDITY", "value": liquidity_type or None},
            {"code": "MINIMUM_INVESTMENT", "value": minimum},
        ],
        "rule_traces": traces,
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
    }
    return FixedIncomeEvaluation.model_validate(result).model_dump()

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any

DISCLAIMER = "Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno."
FORBIDDEN_GUARANTEE_TERMS = ("garantido", "certeza de lucro")


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _money(value: Any) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def _score(value: Any) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"))


def _clamp(value: Decimal, minimum: Decimal = Decimal("0"), maximum: Decimal = Decimal("100")) -> Decimal:
    return max(minimum, min(maximum, value))


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _context_get(context: dict[str, Any] | None, key: str, default: Any = None) -> Any:
    return (context or {}).get(key, default)


def _format_profile(profile: str | None) -> str:
    labels = {
        "CONSERVATIVE": "conservador",
        "MODERATE": "moderado",
        "AGGRESSIVE": "agressivo",
    }
    return labels.get((profile or "MODERATE").upper(), (profile or "moderado").lower())


def _trend_text(trend_label: str | None) -> str:
    return {
        "UPTREND": "de alta",
        "SIDEWAYS": "lateral",
        "DOWNTREND": "de queda",
        "INSUFFICIENT_HISTORY": "com histórico insuficiente",
        "UNKNOWN": "indefinida",
        None: "indefinida",
    }.get(trend_label, str(trend_label).lower())


def _confidence_text(trend_confidence: str | None) -> str:
    return {
        "HIGH": "alta",
        "MEDIUM": "média",
        "LOW": "baixa",
        "VERY_LOW": "muito baixa",
        "UNKNOWN": "indefinida",
        None: "indefinida",
    }.get(trend_confidence, str(trend_confidence).lower())


def _percentile_label(rank: int, total: int) -> str:
    if total <= 0 or rank <= 0:
        return "UNKNOWN"
    percentile = Decimal(rank) / Decimal(total)
    if percentile <= Decimal("0.05"):
        return "TOP_5_PERCENT"
    if percentile <= Decimal("0.10"):
        return "TOP_10_PERCENT"
    if percentile <= Decimal("0.25"):
        return "TOP_25_PERCENT"
    if percentile <= Decimal("0.50"):
        return "TOP_50_PERCENT"
    return "BOTTOM_50_PERCENT"


def calculate_appreciation_signal(
    *,
    recommendation_score: Decimal,
    trend_label: str | None,
    momentum_score: Decimal,
    trend_confidence: str | None,
) -> str:
    trend = (trend_label or "UNKNOWN").upper()
    confidence = (trend_confidence or "UNKNOWN").upper()

    if confidence == "VERY_LOW" or trend == "INSUFFICIENT_HISTORY":
        return "UNKNOWN"
    if trend == "DOWNTREND" or recommendation_score < Decimal("60"):
        return "LOW"
    if (
        recommendation_score >= Decimal("80")
        and trend == "UPTREND"
        and momentum_score >= Decimal("42")
        and confidence in {"MEDIUM", "HIGH"}
    ):
        return "HIGH"
    if recommendation_score >= Decimal("70") and trend in {"UPTREND", "SIDEWAYS"} and confidence in {"LOW", "MEDIUM", "HIGH"}:
        return "MODERATE"
    return "LOW"


def build_appreciation_text(signal: str, trend_label: str | None, trend_confidence: str | None) -> str:
    signal = (signal or "UNKNOWN").upper()
    if signal == "HIGH":
        return (
            "O ativo apresenta sinal quantitativo forte de valorização estimada, combinando tendência positiva, "
            "bom momentum e alta pontuação de recomendação. Ainda assim, não há garantia de retorno."
        )
    if signal == "MODERATE":
        return (
            "O ativo apresenta sinal moderado de valorização estimada. A recomendação é sustentada por bons fundamentos "
            "e risco controlado, mas a tendência ainda não indica força clara de alta, sem garantia de retorno."
        )
    if signal == "LOW":
        return (
            "O ativo apresenta sinal fraco de valorização estimada no momento, principalmente por tendência "
            "desfavorável ou baixa pontuação de recomendação."
        )
    return "Não há histórico suficiente para estimar o sinal de valorização com boa confiança."


def calculate_confidence_score(item: Any) -> Decimal:
    score = _decimal(_get(item, "recommendation_score"))
    status = (_get(item, "status", "") or "").upper()
    risk_level = (_get(item, "risk_level", "") or "").upper()
    trend_confidence = (_get(item, "trend_confidence", "") or "").upper()

    if status == "APPROVED":
        score += Decimal("5")
    if risk_level == "LOW":
        score += Decimal("5")
    if trend_confidence == "HIGH":
        score += Decimal("5")
    elif trend_confidence == "MEDIUM":
        score += Decimal("3")
    elif trend_confidence == "LOW":
        score -= Decimal("5")
    if status == "WARNING":
        score -= Decimal("15")
    if risk_level == "HIGH":
        score -= Decimal("20")
    return _clamp(score).quantize(Decimal("0.01"))


def confidence_label(confidence_score: Decimal) -> str:
    if confidence_score >= Decimal("80"):
        return "HIGH"
    if confidence_score >= Decimal("60"):
        return "MEDIUM"
    return "LOW"


def explanation_quality(*, confidence: str, trend_confidence: str | None, recommendation_score: Decimal) -> str:
    trend_conf = (trend_confidence or "UNKNOWN").upper()
    if confidence == "HIGH" and trend_conf in {"MEDIUM", "HIGH"} and recommendation_score >= Decimal("75"):
        return "STRONG"
    if confidence in {"MEDIUM", "HIGH"} and recommendation_score >= Decimal("60"):
        return "GOOD"
    return "BASIC"


def build_score_breakdown(item: Any) -> dict[str, Decimal]:
    return {
        "recommendation_score": _score(_get(item, "recommendation_score")),
        "fundamental_score": _score(_get(item, "score_total")),
        "profile_score": _score(_get(item, "profile_score")),
        "quality_score": _score(_get(item, "score_quality")),
        "liquidity_score": _score(_get(item, "score_liquidity")),
        "risk_score": _score(_get(item, "score_risk")),
        "dividend_score": _score(_get(item, "score_dividend")),
        "momentum_score": _score(_get(item, "momentum_score")),
    }


def build_decision_card(
    item: Any,
    *,
    invested_amount: Decimal,
    remaining_budget: Decimal,
    budget_usage_pct: Decimal,
    confidence: Decimal,
    appreciation_signal: str,
) -> dict[str, Any]:
    return {
        "ticker": _get(item, "ticker", ""),
        "action": "BUY_CANDIDATE",
        "quantity": int(_get(item, "quantity_possible", _get(item, "quantity", 0)) or 0),
        "price": _money(_get(item, "price")),
        "invested_amount": invested_amount,
        "remaining_budget": remaining_budget,
        "budget_usage_pct": budget_usage_pct,
        "recommendation_score": _score(_get(item, "recommendation_score")),
        "confidence_score": confidence,
        "appreciation_signal": appreciation_signal,
    }


def build_relative_position(context: dict[str, Any] | None) -> dict[str, Any]:
    rank = int(_context_get(context, "recommendation_rank", 1) or 1)
    total = int(_context_get(context, "total_candidates", 1) or 1)
    return {
        "rank": rank,
        "total_candidates": total,
        "percentile_label": _percentile_label(rank, total),
        "text": f"Este ativo ficou em {rank}º lugar entre {total} opção(ões) compatíveis com seu orçamento e perfil.",
    }


def build_strengths(item: Any, *, budget_usage_pct: Decimal) -> list[str]:
    strengths: list[str] = []
    profile_score = _score(_get(item, "profile_score"))
    quality_score = _score(_get(item, "score_quality"))
    liquidity_score = _score(_get(item, "score_liquidity"))
    risk_score = _score(_get(item, "score_risk"))
    dividend_score = _score(_get(item, "score_dividend"))
    recommendation_score = _score(_get(item, "recommendation_score"))

    if profile_score >= Decimal("70"):
        strengths.append(f"Score de perfil alto: {profile_score}/100")
    if quality_score >= Decimal("70"):
        strengths.append(f"Qualidade elevada: {quality_score}/100")
    if liquidity_score >= Decimal("70"):
        strengths.append(f"Liquidez forte: {liquidity_score}/100")
    if risk_score >= Decimal("70"):
        strengths.append(f"Risco controlado: {risk_score}/100")
    if dividend_score >= Decimal("70"):
        strengths.append(f"Dividendos com boa pontuação quantitativa: {dividend_score}/100")
    if recommendation_score >= Decimal("70"):
        strengths.append(f"Score final de recomendação competitivo: {recommendation_score}/100")
    if budget_usage_pct >= Decimal("85"):
        strengths.append(f"Aproveitamento do orçamento: {budget_usage_pct}%")
    if not strengths:
        strengths.append("Ativo passou pelos filtros quantitativos disponíveis para o orçamento informado.")
    return strengths


def build_attention_points(item: Any, *, remaining_budget: Decimal, budget_value: Decimal) -> list[str]:
    points: list[str] = []
    trend_label = (_get(item, "trend_label") or "UNKNOWN").upper()
    trend_confidence = (_get(item, "trend_confidence") or "UNKNOWN").upper()
    momentum_score = _decimal(_get(item, "momentum_score"))
    status = (_get(item, "status") or "").upper()
    risk_level = (_get(item, "risk_level") or "").upper()

    if trend_label == "SIDEWAYS":
        points.append("A tendência atual está lateral, então o sinal de valorização não é forte.")
    elif trend_label == "DOWNTREND":
        points.append("A tendência atual está desfavorável e reduz a atratividade de curto prazo.")
    elif trend_label == "INSUFFICIENT_HISTORY":
        points.append("O histórico ainda é insuficiente para avaliar tendência com boa qualidade.")
    if trend_confidence == "LOW":
        points.append("A confiança da tendência ainda é baixa por histórico curto.")
    elif trend_confidence == "VERY_LOW":
        points.append("A confiança da tendência é muito baixa, então o sinal deve ser lido com cautela.")
    if budget_value > 0 and remaining_budget / budget_value >= Decimal("0.20"):
        points.append("Parte relevante do orçamento ficaria sem uso.")
    if momentum_score < Decimal("45"):
        points.append("Momentum ainda moderado, sem força clara de alta.")
    if status == "WARNING":
        points.append("O ativo possui alerta nos guardrails e só aparece quando alertas são permitidos.")
    if risk_level == "HIGH":
        points.append("O risco classificado como alto exige cautela adicional antes de qualquer decisão.")
    if not points:
        points.append("Nenhum alerta quantitativo crítico foi identificado dentro das regras atuais.")
    return points


def build_why_recommended(item: Any, *, budget_usage_pct: Decimal | None = None) -> list[str]:
    reasons: list[str] = []
    ticker = _get(item, "ticker", "")
    status = (_get(item, "status", "") or "").upper()
    risk_level = (_get(item, "risk_level", "") or "").upper()
    profile = _format_profile(_get(item, "profile", "MODERATE"))
    trend = (_get(item, "trend_label") or "UNKNOWN").upper()
    trend_confidence = (_get(item, "trend_confidence") or "UNKNOWN").upper()

    if status == "APPROVED":
        reasons.append(f"{ticker} foi aprovado pelos guardrails e classificado como risco {risk_level.lower() or 'controlado'}.")
    elif status == "WARNING":
        reasons.append(f"{ticker} possui alerta nos guardrails, mas foi mantido porque alertas foram permitidos.")
    reasons.append(f"O ativo obteve profile_score de {_score(_get(item, 'profile_score'))} para perfil {profile}.")
    reasons.append(f"O score fundamentalista ficou em {_score(_get(item, 'score_total'))}/100.")
    reasons.append(f"A qualidade do ativo ficou em {_score(_get(item, 'score_quality'))}/100.")
    reasons.append(f"A liquidez ficou em {_score(_get(item, 'score_liquidity'))}/100.")
    reasons.append(f"O score de risco ficou em {_score(_get(item, 'score_risk'))}/100.")
    reasons.append(f"O score de dividendos ficou em {_score(_get(item, 'score_dividend'))}/100.")
    if budget_usage_pct is not None:
        reasons.append(f"O orçamento foi aproveitado em {budget_usage_pct}% do valor disponível.")
    reasons.append(f"A tendência atual é {_trend_text(trend)} com confiança {_confidence_text(trend_confidence)}.")
    return reasons


def build_comparison_with_alternatives(item: Any, context: dict[str, Any] | None) -> list[dict[str, str]]:
    current_score = _decimal(_get(item, "recommendation_score"))
    current_momentum = _decimal(_get(item, "momentum_score"))
    comparisons: list[dict[str, str]] = []
    for alternative in list(_context_get(context, "alternatives", []) or [])[:3]:
        alt_ticker = _get(alternative, "ticker", "")
        alt_score = _decimal(_get(alternative, "recommendation_score"))
        alt_momentum = _decimal(_get(alternative, "momentum_score"))
        if alt_score < current_score and alt_momentum < current_momentum:
            reason = "Ficou abaixo por ter recommendation_score menor e momentum inferior."
        elif alt_score < current_score:
            reason = "Ficou abaixo por ter recommendation_score menor no ranking final."
        elif alt_momentum < current_momentum:
            reason = "Ficou abaixo principalmente por momentum inferior."
        else:
            reason = "Ficou abaixo após a combinação de perfil, risco, fundamentos e tendência."
        comparisons.append({"ticker": alt_ticker, "reason": reason})
    return comparisons


def build_executive_summary(
    item: Any,
    *,
    budget_value: Decimal,
    invested_amount: Decimal,
    budget_usage_pct: Decimal,
    confidence: str,
) -> str:
    ticker = _get(item, "ticker", "")
    quantity = int(_get(item, "quantity_possible", _get(item, "quantity", 0)) or 0)
    profile = _format_profile(_get(item, "profile", "MODERATE"))
    confidence_text = {"HIGH": "alta", "MEDIUM": "média", "LOW": "baixa"}.get(confidence, "baixa")
    return (
        f"Para um orçamento de R${budget_value.quantize(Decimal('0.01'))}, o ativo mais indicado foi {ticker}. "
        f"Ele permite comprar {quantity} cota(s), utiliza {budget_usage_pct}% do orçamento e apresenta "
        f"confiança quantitativa {confidence_text} para o perfil {profile}."
    )


def build_recommendation_explanation(
    item: Any,
    context: dict[str, Any] | None = None,
    *,
    budget: Decimal | int | str | None = None,
    summary: bool = False,
) -> dict[str, Any]:
    budget_value = _decimal(
        budget if budget is not None else _context_get(context, "budget", _get(item, "budget")),
        default=Decimal("0"),
    )
    price = _money(_get(item, "price"))
    invested_amount = _money(_get(item, "invested_amount"))
    quantity = int(_get(item, "quantity_possible", _get(item, "quantity", 0)) or 0)
    ticker = _get(item, "ticker", "")
    profile = (_get(item, "profile", _context_get(context, "profile", "MODERATE")) or "MODERATE").upper()
    profile_label = _format_profile(profile)
    recommendation_score = _decimal(_get(item, "recommendation_score"))
    momentum_score = _decimal(_get(item, "momentum_score"))
    trend_label = _get(item, "trend_label")
    trend_confidence = _get(item, "trend_confidence")

    remaining_budget = _money(budget_value - invested_amount) if budget_value > 0 else Decimal("0.00")
    budget_usage_pct = Decimal("0.00")
    if budget_value > 0:
        budget_usage_pct = _clamp((invested_amount / budget_value) * Decimal("100")).quantize(Decimal("0.01"))

    appreciation_signal = calculate_appreciation_signal(
        recommendation_score=recommendation_score,
        trend_label=trend_label,
        momentum_score=momentum_score,
        trend_confidence=trend_confidence,
    )
    confidence = calculate_confidence_score(item)
    conf_label = confidence_label(confidence)

    explanation = {
        "recommendation_title": f"Melhor opção para seu perfil {profile_label}" if not summary else f"Alternativa para perfil {profile_label}",
        "decision_summary": (
            f"Com R${budget_value.quantize(Decimal('0.01'))}, você consegue comprar {quantity} cota(s) de {ticker}, "
            f"investindo aproximadamente R${invested_amount}."
        ),
        "executive_summary": build_executive_summary(
            item,
            budget_value=budget_value,
            invested_amount=invested_amount,
            budget_usage_pct=budget_usage_pct,
            confidence=conf_label,
        ),
        "decision_card": build_decision_card(
            item,
            invested_amount=invested_amount,
            remaining_budget=remaining_budget,
            budget_usage_pct=budget_usage_pct,
            confidence=confidence,
            appreciation_signal=appreciation_signal,
        ),
        "score_breakdown": build_score_breakdown(item),
        "relative_position": build_relative_position(context),
        "strengths": build_strengths(item, budget_usage_pct=budget_usage_pct),
        "attention_points": build_attention_points(item, remaining_budget=remaining_budget, budget_value=budget_value),
        "comparison_with_alternatives": build_comparison_with_alternatives(item, context) if not summary else [],
        "why_recommended": build_why_recommended(item, budget_usage_pct=budget_usage_pct),
        "appreciation_signal": appreciation_signal,
        "appreciation_text": build_appreciation_text(appreciation_signal, trend_label, trend_confidence),
        "confidence_score": confidence,
        "confidence_label": conf_label,
        "explanation_quality": explanation_quality(
            confidence=conf_label,
            trend_confidence=trend_confidence,
            recommendation_score=recommendation_score,
        ),
        "budget_usage_pct": budget_usage_pct,
        "remaining_budget": remaining_budget,
        "disclaimer": DISCLAIMER,
    }
    return explanation


def enrich_item_with_explanation(
    item: Any,
    *,
    budget: Decimal | int | str,
    summary: bool = False,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = item if isinstance(item, dict) else item.__dict__.copy()
    merged_context = dict(context or {})
    merged_context.setdefault("budget", budget)
    base.update(build_recommendation_explanation(base, context=merged_context, budget=budget, summary=summary))
    return base

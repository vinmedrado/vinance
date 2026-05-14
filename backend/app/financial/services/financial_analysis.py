from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.app.core.services.personal_finance import get_core_summary
from backend.app.financing.schemas import FinancingSimulationRequest
from backend.app.financing.services.calculator import FinancingInput, calculate_schedule

SAFE_COMMITMENT = 0.25
COMFORT_COMMITMENT = 0.30
MODERATE_COMMITMENT = 0.35
MAX_COMMITMENT = 0.40
CRITICAL_COMMITMENT = 0.45
MIN_RESERVE_AFTER_PAYMENT = 0.10
IDEAL_RESERVE_AFTER_PAYMENT = 0.15


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _money(value: float | int | None) -> str:
    return f"R$ {_round(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%".replace(".", ",")


def get_financial_summary() -> dict[str, Any]:
    core = get_core_summary()
    renda_total = _round(core.get("renda_mensal_estimada") or core.get("receitas_total"))
    despesas_totais = _round(core.get("gasto_mensal_estimado") or core.get("despesas_pendentes") or core.get("despesas_total"))
    despesas_pendentes = _round(core.get("despesas_pendentes"))
    despesas_pagas = _round(core.get("despesas_pagas"))
    saldo_mensal = _round(renda_total - despesas_totais)
    saldo_disponivel = max(0.0, saldo_mensal)
    capacidade_pagamento = _round(min(renda_total * SAFE_COMMITMENT, saldo_disponivel * 0.80)) if renda_total > 0 else 0.0
    comprometimento_atual_pct = round(despesas_totais / renda_total, 6) if renda_total > 0 else None

    return {
        "renda_total": renda_total,
        "despesas_totais": despesas_totais,
        "despesas_pendentes": despesas_pendentes,
        "despesas_pagas": despesas_pagas,
        "saldo_mensal": saldo_mensal,
        "saldo_disponivel": saldo_disponivel,
        "capacidade_pagamento": capacidade_pagamento,
        "comprometimento_atual_pct": comprometimento_atual_pct,
        "fonte": "core_financas_db",
        "core": core,
    }


def get_financial_capacity() -> dict[str, Any]:
    summary = get_financial_summary()
    renda = summary["renda_total"]
    saldo = summary["saldo_disponivel"]
    capacidade_segura = _round(min(renda * SAFE_COMMITMENT, saldo * 0.80)) if renda > 0 else 0.0
    capacidade_moderada = _round(min(renda * MODERATE_COMMITMENT, saldo * 0.90)) if renda > 0 else 0.0
    limite_maximo = _round(min(renda * MAX_COMMITMENT, saldo)) if renda > 0 else 0.0

    if renda <= 0:
        texto = "Cadastre sua renda no módulo core antes de assumir um financiamento. Sem renda informada, a análise fica incompleta."
    elif saldo <= 0:
        texto = "No cenário atual, suas despesas consomem toda a renda. Antes de financiar, reduza despesas ou aumente a renda."
    else:
        texto = f"Parcela segura estimada até {_money(capacidade_segura)}; acima de {_money(capacidade_moderada)} já exige atenção."

    return {
        **summary,
        "capacidade_segura": capacidade_segura,
        "capacidade_moderada": capacidade_moderada,
        "limite_maximo_recomendado": limite_maximo,
        "recomendacao_textual": texto,
    }


def _finance_input_from_request(payload: FinancingSimulationRequest, monthly_income: float | None) -> FinancingInput:
    data = payload.model_dump()
    if monthly_income and not data.get("monthly_income"):
        data["monthly_income"] = monthly_income
    return FinancingInput(**data)


def _safe_model_copy(payload: FinancingSimulationRequest, **updates: Any) -> FinancingSimulationRequest:
    # Pydantic v2 tem model_copy; este fallback preserva compatibilidade em ambientes mistos.
    if hasattr(payload, "model_copy"):
        return payload.model_copy(update=updates)
    data = payload.dict()
    data.update(updates)
    return FinancingSimulationRequest(**data)


def _build_reasons(
    parcela: float,
    renda: float,
    despesas: float,
    saldo: float,
    risk_level: str,
    months: int,
    ltv_pct: float,
    total_interest: float,
    asset_value: float,
) -> list[str]:
    reasons: list[str] = []
    if renda <= 0:
        return ["Renda mensal não informada; sem renda não dá para medir comprometimento com segurança."]

    parcela_commitment = parcela / renda
    total_commitment = (despesas + parcela) / renda
    sobra = saldo - parcela
    reserva_minima = renda * MIN_RESERVE_AFTER_PAYMENT
    reserva_ideal = renda * IDEAL_RESERVE_AFTER_PAYMENT

    if parcela_commitment > CRITICAL_COMMITMENT:
        reasons.append(f"Sua parcela compromete {_pct(parcela_commitment)} da renda, acima do nível crítico de {_pct(CRITICAL_COMMITMENT)}.")
    elif parcela_commitment > MAX_COMMITMENT:
        reasons.append(f"Sua parcela compromete {_pct(parcela_commitment)} da renda, acima do limite recomendado de {_pct(MAX_COMMITMENT)}.")
    elif parcela_commitment > MODERATE_COMMITMENT:
        reasons.append(f"Sua parcela compromete {_pct(parcela_commitment)} da renda, entrando em faixa arriscada.")
    elif parcela_commitment > SAFE_COMMITMENT:
        reasons.append(f"Sua parcela compromete {_pct(parcela_commitment)} da renda; cabe no orçamento, mas já reduz margem de segurança.")
    else:
        reasons.append(f"A parcela compromete {_pct(parcela_commitment)} da renda, dentro da faixa segura de até {_pct(SAFE_COMMITMENT)}.")

    if parcela > saldo:
        reasons.append(f"A parcela de {_money(parcela)} é maior que o saldo disponível de {_money(saldo)}.")
    elif sobra < reserva_minima:
        reasons.append(f"Depois da parcela sobrariam {_money(sobra)}, abaixo da reserva mínima mensal de {_money(reserva_minima)}.")
    elif sobra < reserva_ideal:
        reasons.append(f"Depois da parcela sobrariam {_money(sobra)}, abaixo da margem confortável de {_money(reserva_ideal)}.")
    else:
        reasons.append(f"Após pagar a parcela, ainda sobrariam {_money(sobra)} no mês.")

    if total_commitment > 0.80:
        reasons.append(f"Somando despesas atuais e financiamento, o orçamento fica {_pct(total_commitment)} comprometido.")
    elif total_commitment > 0.70:
        reasons.append(f"O comprometimento total chega a {_pct(total_commitment)}, exigindo controle forte de gastos.")

    if months > 180:
        reasons.append("Prazo muito longo aumenta o custo total e mantém a dívida ativa por muitos anos.")
    elif months > 96:
        reasons.append("Prazo longo reduz a parcela, mas aumenta bastante o impacto de juros no longo prazo.")

    if ltv_pct > 0.85:
        reasons.append(f"Entrada baixa: você financiaria {_pct(ltv_pct)} do bem, elevando risco e juros totais.")

    if asset_value > 0 and total_interest / asset_value > 0.45:
        reasons.append(f"Juros totais equivalem a {_pct(total_interest / asset_value)} do valor do bem, impacto relevante no longo prazo.")

    if risk_level == "alto":
        reasons.append("O motor de financiamento marcou risco alto pelos parâmetros de entrada, prazo, taxa e comprometimento.")

    return reasons[:6]


def _build_recommendations(classificacao: str, parcela: float, capacidade: float, saldo: float) -> list[str]:
    recs: list[str] = []
    if classificacao == "seguro":
        recs.append("Cenário saudável: mantenha reserva mensal e compare taxas antes de contratar.")
        recs.append("Mesmo aprovado, prefira a opção com menor CET e menor custo total, não apenas menor parcela.")
    elif classificacao == "moderado":
        recs.append("Aumentar a entrada melhora a margem de segurança e reduz juros no longo prazo.")
        recs.append("Compare um prazo um pouco menor: se a parcela continuar cabendo, o custo total cai.")
        recs.append("Evite novas dívidas até criar uma folga mensal mais confortável.")
    else:
        recs.append("Reduza o valor financiado com uma entrada maior antes de contratar.")
        recs.append("Busque uma parcela menor, idealmente próxima da capacidade segura calculada.")
        recs.append("Reorganize despesas fixas para recuperar margem mensal antes de assumir a dívida.")
    if capacidade > 0 and parcela > capacidade:
        recs.append(f"Tente aproximar a parcela de {_money(capacidade)}, que é a capacidade segura estimada.")
    if saldo > 0 and parcela > saldo * 0.80:
        recs.append("A parcela consome quase toda a sobra mensal; preserve caixa para imprevistos.")
    return recs[:5]


def _classify(parcela: float, renda: float, despesas: float, saldo: float, risk_level: str) -> tuple[str, bool, str, float | None, float | None, float | None]:
    if renda <= 0:
        return "arriscado", False, "Não recomendo financiar sem renda mensal cadastrada ou informada.", None, None, None

    parcela_commitment = parcela / renda
    total_commitment = (despesas + parcela) / renda
    sobra_apos_parcela = saldo - parcela
    reserva_ratio = sobra_apos_parcela / renda if renda > 0 else None
    reserva_minima = renda * MIN_RESERVE_AFTER_PAYMENT
    reserva_ideal = renda * IDEAL_RESERVE_AFTER_PAYMENT

    if parcela > saldo or parcela_commitment > CRITICAL_COMMITMENT or total_commitment > 0.85:
        return (
            "arriscado",
            False,
            "Não recomendo financiar neste formato: a parcela pressiona demais o orçamento e reduz sua margem de segurança.",
            parcela_commitment,
            total_commitment,
            reserva_ratio,
        )

    if (
        parcela_commitment <= SAFE_COMMITMENT
        and total_commitment <= 0.60
        and sobra_apos_parcela >= reserva_ideal
        and risk_level in {"baixo", "medio"}
    ):
        return (
            "seguro",
            True,
            "Pode financiar com boa margem: a parcela cabe na renda, preserva sobra mensal e mantém risco controlado.",
            parcela_commitment,
            total_commitment,
            reserva_ratio,
        )

    if parcela_commitment <= MODERATE_COMMITMENT and total_commitment <= 0.75 and sobra_apos_parcela >= reserva_minima:
        return (
            "moderado",
            True,
            "Financiamento possível, mas exige controle: cabe no orçamento, porém reduz a folga mensal.",
            parcela_commitment,
            total_commitment,
            reserva_ratio,
        )

    return (
        "arriscado",
        False,
        "Não recomendo financiar neste formato: entrada, prazo, taxa ou parcela deixam o orçamento pressionado.",
        parcela_commitment,
        total_commitment,
        reserva_ratio,
    )


def _scenario_payloads(financing: FinancingSimulationRequest) -> list[tuple[str, str, FinancingSimulationRequest]]:
    asset_value = float(financing.asset_value)
    current_down = float(financing.down_payment)
    max_down = max(0.0, asset_value - 1.0)
    extra_down = min(max_down, max(current_down + asset_value * 0.10, current_down * 1.25))
    smaller_months = max(1, int(round(financing.months * 0.80)))
    longer_months = min(420, max(financing.months + 12, int(round(financing.months * 1.20))))

    scenarios = [
        ("cenario_atual", "Cenário atual", financing),
    ]
    if extra_down > current_down:
        scenarios.append(("entrada_maior", "Entrada maior", _safe_model_copy(financing, down_payment=round(extra_down, 2))))
    if smaller_months < financing.months:
        scenarios.append(("prazo_menor", "Prazo menor", _safe_model_copy(financing, months=smaller_months)))
    if longer_months > financing.months:
        scenarios.append(("parcela_reduzida", "Parcela reduzida", _safe_model_copy(financing, months=longer_months)))
    return scenarios


def _analyze_single(financing: FinancingSimulationRequest, renda: float, despesas: float, saldo: float, capacidade: float) -> dict[str, Any]:
    simulation = calculate_schedule(_finance_input_from_request(financing, renda if renda > 0 else None))
    parcela = _round(simulation.get("first_payment"))
    classificacao, pode, texto, pct_parcela, pct_total, reserva_ratio = _classify(
        parcela,
        renda,
        despesas,
        saldo,
        simulation.get("risk_level", "alto"),
    )
    reasons = _build_reasons(
        parcela=parcela,
        renda=renda,
        despesas=despesas,
        saldo=saldo,
        risk_level=simulation.get("risk_level", "alto"),
        months=int(simulation.get("months") or financing.months),
        ltv_pct=float(simulation.get("ltv_pct") or 0),
        total_interest=float(simulation.get("total_interest") or 0),
        asset_value=float(simulation.get("asset_value") or financing.asset_value),
    )
    recommendations = _build_recommendations(classificacao, parcela, capacidade, saldo)

    return {
        "parcela_simulada": parcela,
        "percentual_comprometimento": round(pct_parcela, 6) if pct_parcela is not None else None,
        "comprometimento_total_pct": round(pct_total, 6) if pct_total is not None else None,
        "margem_apos_parcela": _round(saldo - parcela),
        "margem_apos_parcela_pct": round(reserva_ratio, 6) if reserva_ratio is not None else None,
        "classificacao": classificacao,
        "pode_financiar": pode,
        "recomendacao_textual": texto,
        "motivos": reasons,
        "como_melhorar": recommendations,
        "financing_result": simulation,
    }


def _build_scenarios(financing: FinancingSimulationRequest, renda: float, despesas: float, saldo: float, capacidade: float) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for key, label, scenario_financing in _scenario_payloads(financing):
        analyzed = _analyze_single(scenario_financing, renda, despesas, saldo, capacidade)
        result = analyzed["financing_result"]
        scenarios.append({
            "cenario": key,
            "titulo": label,
            "classificacao": analyzed["classificacao"],
            "pode_financiar": analyzed["pode_financiar"],
            "parcela": analyzed["parcela_simulada"],
            "comprometimento_pct": analyzed["percentual_comprometimento"],
            "margem_apos_parcela": analyzed["margem_apos_parcela"],
            "custo_total": _round(result.get("total_cost")),
            "juros_total": _round(result.get("total_interest")),
            "cet_anual": result.get("estimated_cet_annual"),
            "entrada": _round(result.get("down_payment")),
            "prazo": int(result.get("months") or 0),
            "recomendacao": analyzed["recomendacao_textual"],
        })
    return scenarios


def _pick_best_scenario(scenarios: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not scenarios:
        return None
    rank = {"seguro": 0, "moderado": 1, "arriscado": 2}
    return sorted(
        scenarios,
        key=lambda s: (
            rank.get(s["classificacao"], 9),
            s["juros_total"],
            s["parcela"],
        ),
    )[0]


def analyze_financing_decision(
    financing: FinancingSimulationRequest,
    renda_mensal: float | None = None,
    despesas_mensais: float | None = None,
    saldo_disponivel: float | None = None,
    usar_dados_core: bool = True,
) -> dict[str, Any]:
    core_summary = get_core_summary() if usar_dados_core else {}
    summary = get_financial_summary() if usar_dados_core else {
        "renda_total": _round(renda_mensal),
        "despesas_totais": _round(despesas_mensais),
        "saldo_mensal": _round((renda_mensal or 0) - (despesas_mensais or 0)),
        "saldo_disponivel": _round(saldo_disponivel if saldo_disponivel is not None else (renda_mensal or 0) - (despesas_mensais or 0)),
        "capacidade_pagamento": 0.0,
    }

    renda = _round(renda_mensal if renda_mensal is not None else summary.get("renda_total"))
    despesas = _round(despesas_mensais if despesas_mensais is not None else summary.get("despesas_totais"))
    saldo = _round(saldo_disponivel if saldo_disponivel is not None else summary.get("saldo_disponivel"))
    capacidade = _round(min(renda * SAFE_COMMITMENT, max(0.0, saldo) * 0.80)) if renda > 0 else 0.0

    analyzed = _analyze_single(financing, renda, despesas, saldo, capacidade)
    scenarios = _build_scenarios(financing, renda, despesas, saldo, capacidade)
    best = _pick_best_scenario(scenarios)

    return {
        "renda_total": renda,
        "despesas_totais": despesas,
        "saldo_mensal": _round(renda - despesas),
        "saldo_disponivel": saldo,
        "capacidade_pagamento": capacidade,
        "parcela_simulada": analyzed["parcela_simulada"],
        "percentual_comprometimento": analyzed["percentual_comprometimento"],
        "comprometimento_total_pct": analyzed["comprometimento_total_pct"],
        "margem_apos_parcela": analyzed["margem_apos_parcela"],
        "margem_apos_parcela_pct": analyzed["margem_apos_parcela_pct"],
        "classificacao": analyzed["classificacao"],
        "pode_financiar": analyzed["pode_financiar"],
        "recomendacao_textual": analyzed["recomendacao_textual"],
        "motivos": analyzed["motivos"],
        "como_melhorar": analyzed["como_melhorar"],
        "cenarios": scenarios,
        "melhor_cenario": best,
        "financing_result": analyzed["financing_result"],
        "core_summary": core_summary,
    }

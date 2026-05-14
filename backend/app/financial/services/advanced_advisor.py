from __future__ import annotations

from typing import Any

DECISION_LABELS = {
    "seguro": "Seguro",
    "moderado": "Recomendado com ajustes",
    "arriscado": "Não recomendado",
}


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _money(value: float | int | None) -> str:
    return f"R$ {_round(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float | int | None) -> str:
    if value is None:
        return "não calculado"
    return f"{float(value) * 100:.1f}%".replace(".", ",")


def _rank(classification: str | None) -> int:
    return {"seguro": 0, "moderado": 1, "arriscado": 2}.get(str(classification or "moderado"), 1)


def _class_from_score(score: int) -> str:
    if score >= 75:
        return "arriscado"
    if score >= 40:
        return "moderado"
    return "seguro"


def _monthly_surplus(income: float, expenses: float, monthly_payment: float = 0.0, investment_target: float = 0.0) -> float:
    return _round(income - expenses - monthly_payment - investment_target)


def build_priority_engine(
    *,
    income: float,
    expenses: float,
    emergency_reserve: float,
    reserve_months_target: float = 6.0,
    monthly_payment: float = 0.0,
    investment_target: float = 0.0,
    risk_profile: str = "conservador",
) -> dict[str, Any]:
    """Identifica o gargalo principal e devolve uma ação única, humana e prática."""
    income = _round(income)
    expenses = _round(expenses)
    emergency_reserve = _round(emergency_reserve)
    monthly_payment = _round(monthly_payment)
    investment_target = _round(investment_target)
    balance = _monthly_surplus(income, expenses, monthly_payment, investment_target)
    gross_balance = _round(income - expenses - monthly_payment)
    commitment = (expenses + monthly_payment) / income if income > 0 else None
    reserve_months = emergency_reserve / expenses if expenses > 0 else 0.0

    problems: list[dict[str, Any]] = []
    if income <= 0:
        problems.append({
            "problema": "renda_nao_cadastrada",
            "titulo": "Renda mensal não cadastrada",
            "gravidade": 100,
            "explicacao": "Sem renda mensal, o FinanceOS não consegue decidir com segurança quanto você pode financiar, poupar ou investir.",
            "acao": "Cadastrar a renda mensal e revisar as despesas fixas antes de qualquer decisão financeira.",
        })
    if gross_balance < 0:
        problems.append({
            "problema": "saldo_negativo",
            "titulo": "O mês fecha negativo",
            "gravidade": 95,
            "explicacao": f"Depois de despesas e parcelas, faltam {_money(abs(gross_balance))} para fechar o mês.",
            "acao": "Cortar ou renegociar despesas antes de assumir novas parcelas ou investimentos.",
        })
    if commitment is not None and commitment >= 0.85:
        problems.append({
            "problema": "renda_muito_comprometida",
            "titulo": "Renda muito comprometida",
            "gravidade": 90,
            "explicacao": f"Despesas e parcelas consomem {_pct(commitment)} da renda. Isso deixa pouca margem para imprevistos.",
            "acao": "Não assumir nova dívida e reduzir despesas fixas até o comprometimento cair para perto de 60%.",
        })
    elif commitment is not None and commitment >= 0.70:
        problems.append({
            "problema": "renda_pressionada",
            "titulo": "Renda pressionada",
            "gravidade": 68,
            "explicacao": f"O orçamento já usa {_pct(commitment)} da renda. A decisão ainda pode ser ajustada, mas exige cautela.",
            "acao": "Melhorar entrada, reduzir parcela ou adiar a decisão até sobrar mais caixa mensal.",
        })
    if expenses > 0 and reserve_months < 1:
        problems.append({
            "problema": "reserva_critica",
            "titulo": "Reserva de emergência crítica",
            "gravidade": 88,
            "explicacao": f"Sua reserva cobre apenas {reserve_months:.1f} mês(es) de despesas.",
            "acao": "Direcionar a sobra mensal para reserva até completar pelo menos 3 meses de despesas.",
        })
    elif expenses > 0 and reserve_months < min(3, reserve_months_target):
        problems.append({
            "problema": "reserva_baixa",
            "titulo": "Reserva de emergência baixa",
            "gravidade": 62,
            "explicacao": f"Sua reserva cobre {reserve_months:.1f} meses. O alvo configurado é {reserve_months_target:.0f} meses.",
            "acao": "Priorizar reserva antes de aumentar risco em financiamento ou renda variável.",
        })
    if monthly_payment > 0 and income > 0 and monthly_payment / income > 0.35:
        problems.append({
            "problema": "parcela_alta",
            "titulo": "Parcela alta para a renda",
            "gravidade": 82,
            "explicacao": f"A parcela analisada consome {_pct(monthly_payment / income)} da renda mensal.",
            "acao": "Aumentar entrada, reduzir valor financiado ou buscar prazo/taxa que reduza a parcela.",
        })
    if investment_target > 0 and balance < 0:
        problems.append({
            "problema": "meta_investimento_incompativel",
            "titulo": "Meta de investimento maior que a folga real",
            "gravidade": 70,
            "explicacao": "A meta de investimento deixa o caixa mensal negativo quando combinada com despesas e parcelas.",
            "acao": "Reduzir temporariamente o aporte e concentrar dinheiro em caixa e reserva.",
        })
    if risk_profile == "agressivo" and reserve_months < 6:
        problems.append({
            "problema": "risco_investimento_sem_reserva",
            "titulo": "Perfil agressivo sem reserva completa",
            "gravidade": 58,
            "explicacao": "Investir de forma agressiva sem reserva completa aumenta a chance de vender ativos no pior momento.",
            "acao": "Manter investimentos mais líquidos até completar a reserva de emergência.",
        })

    if not problems:
        problems.append({
            "problema": "manter_disciplina",
            "titulo": "Base financeira saudável",
            "gravidade": 15,
            "explicacao": "A renda, a reserva e a sobra mensal permitem decisões com menor risco.",
            "acao": "Manter aportes planejados, comparar custos antes de financiar e revisar metas mensalmente.",
        })

    main = sorted(problems, key=lambda item: item["gravidade"], reverse=True)[0]
    return {
        "problema_mais_critico": main,
        "acao_principal_recomendada": main["acao"],
        "ranking_problemas": sorted(problems, key=lambda item: item["gravidade"], reverse=True),
        "metricas": {
            "saldo_apos_decisoes": balance,
            "saldo_antes_meta_investimento": gross_balance,
            "comprometimento_pct": commitment,
            "meses_reserva": round(reserve_months, 2),
        },
    }


def build_future_projection(
    *,
    income: float,
    expenses: float,
    emergency_reserve: float,
    monthly_payment: float = 0.0,
    planned_monthly_investment: float = 0.0,
    reserve_target: float = 0.0,
) -> list[dict[str, Any]]:
    income = _round(income)
    expenses = _round(expenses)
    emergency_reserve = _round(emergency_reserve)
    monthly_payment = _round(monthly_payment)
    planned_monthly_investment = _round(planned_monthly_investment)
    reserve_target = _round(reserve_target or expenses * 6)
    monthly_free_cash = _round(income - expenses - monthly_payment)
    safe_monthly_build = max(0.0, min(monthly_free_cash, planned_monthly_investment if planned_monthly_investment > 0 else monthly_free_cash * 0.60))

    projection: list[dict[str, Any]] = []
    for months in (6, 12, 24):
        reserve_estimate = _round(emergency_reserve + safe_monthly_build * months)
        reserve_months = _round(reserve_estimate / expenses, 2) if expenses > 0 else 0.0
        target_progress = reserve_estimate / reserve_target if reserve_target > 0 else 0.0
        if monthly_free_cash <= 0:
            status = "arriscado"
            message = f"Em {months} meses, a tendência é continuar sem formar reserva porque o caixa mensal está pressionado."
        elif target_progress >= 1:
            status = "seguro"
            message = f"Em {months} meses, a reserva pode chegar a {_money(reserve_estimate)}, atingindo ou superando a meta."
        elif target_progress >= 0.50:
            status = "moderado"
            message = f"Em {months} meses, a reserva pode chegar a {_money(reserve_estimate)}, ainda abaixo da meta, mas com boa evolução."
        else:
            status = "arriscado"
            message = f"Em {months} meses, a reserva estimada ainda fica baixa: {_money(reserve_estimate)}."
        projection.append({
            "meses": months,
            "saldo_livre_mensal": monthly_free_cash,
            "aporte_considerado": _round(safe_monthly_build),
            "reserva_estimada": reserve_estimate,
            "meses_de_reserva": reserve_months,
            "progresso_reserva_pct": round(min(max(target_progress, 0), 1), 6),
            "classificacao": status,
            "mensagem": message,
        })
    return projection


def build_automatic_plan(*, priority: dict[str, Any], classification: str, profile: dict[str, Any], projection: list[dict[str, Any]]) -> dict[str, Any]:
    main_problem = priority["problema_mais_critico"]
    monthly_balance = priority["metricas"].get("saldo_antes_meta_investimento") or 0.0
    reserve_months = priority["metricas"].get("meses_reserva") or 0.0

    immediate: list[str] = [main_problem["acao"]]
    next_90_days: list[str] = []
    next_12_months: list[str] = []

    if monthly_balance <= 0:
        immediate.append("Congelar novas parcelas até o orçamento voltar a fechar positivo.")
        next_90_days.append("Listar despesas fixas e cortar ou renegociar itens que não sustentam renda, saúde ou trabalho.")
    else:
        immediate.append(f"Separar pelo menos {_money(monthly_balance * 0.50)} por mês para a prioridade principal.")
        next_90_days.append("Automatizar a transferência mensal para reserva ou investimento no dia do recebimento.")

    if reserve_months < 3:
        next_90_days.append("Construir reserva inicial de 3 meses antes de buscar maior rentabilidade.")
    elif reserve_months < float(profile.get("reserva_meses_alvo") or 6):
        next_90_days.append("Completar a reserva alvo antes de elevar risco em investimentos.")
    else:
        next_90_days.append("Manter reserva intacta e investir apenas o excedente mensal planejado.")

    if classification == "arriscado":
        next_12_months.append("Reduzir comprometimento mensal antes de qualquer financiamento novo.")
        next_12_months.append("Revisar metas mensalmente até o status sair de Não recomendado.")
    elif classification == "moderado":
        next_12_months.append("Ajustar entrada, prazo e metas para transformar a decisão em segura.")
        next_12_months.append("Aumentar reserva e manter aportes conservadores enquanto houver dívida relevante.")
    else:
        next_12_months.append("Executar aportes recorrentes e rebalancear investimentos conforme o perfil.")
        next_12_months.append("Comparar oportunidades de financiamento pelo custo total, não só pela parcela.")

    return {
        "plano_30_dias": immediate[:4],
        "plano_90_dias": next_90_days[:4],
        "plano_12_meses": next_12_months[:4],
        "marco_24_meses": projection[-1]["mensagem"] if projection else "Revisar evolução a cada relatório mensal.",
    }


def build_smart_alerts(current: dict[str, Any], previous_history: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    classification = current.get("classificacao", "moderado")
    balance = float(current.get("saldo_mensal") or 0)
    commitment = current.get("comprometimento_pct")
    reserve_months = float(current.get("meses_reserva") or 0)

    if classification == "arriscado":
        alerts.append({"tipo": "risco", "nivel": "alto", "mensagem": "Seu cenário atual está em Não recomendado. Evite novas dívidas até recuperar margem mensal."})
    if balance < 0:
        alerts.append({"tipo": "caixa", "nivel": "alto", "mensagem": f"O caixa mensal está negativo em {_money(abs(balance))}."})
    if commitment is not None and commitment > 0.80:
        alerts.append({"tipo": "comprometimento", "nivel": "alto", "mensagem": f"A renda está {_pct(commitment)} comprometida, acima do nível saudável."})
    if reserve_months < 1:
        alerts.append({"tipo": "reserva", "nivel": "alto", "mensagem": "A reserva cobre menos de 1 mês de despesas."})

    history = previous_history or []
    if len(history) >= 1:
        last = history[0]
        previous_class = last.get("classification")
        if _rank(classification) > _rank(previous_class):
            alerts.append({"tipo": "piora", "nivel": "medio", "mensagem": "A classificação atual piorou em relação ao último registro histórico."})
        previous_balance = float(last.get("monthly_balance") or 0)
        if balance < previous_balance:
            alerts.append({"tipo": "piora_caixa", "nivel": "medio", "mensagem": f"A sobra mensal caiu de {_money(previous_balance)} para {_money(balance)}."})

    if not alerts:
        alerts.append({"tipo": "monitoramento", "nivel": "baixo", "mensagem": "Nenhum alerta crítico detectado. Mantenha acompanhamento mensal."})
    return alerts


def build_advanced_advisor(
    *,
    profile: dict[str, Any],
    income: float,
    expenses: float,
    emergency_reserve: float,
    investment_target: float = 0.0,
    financing_analysis: dict[str, Any] | None = None,
    investment_advice: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    monthly_payment = float((financing_analysis or {}).get("parcela_simulada") or 0)
    base_balance = _round(income - expenses)
    reserve_months = emergency_reserve / expenses if expenses > 0 else 0.0
    reserve_target = expenses * float(profile.get("reserva_meses_alvo") or 6)
    commitment = (expenses + monthly_payment) / income if income > 0 else None

    risk_score = 0
    if income <= 0:
        risk_score += 100
    if base_balance < 0:
        risk_score += 45
    if commitment is not None:
        if commitment > 0.85:
            risk_score += 45
        elif commitment > 0.70:
            risk_score += 25
    if reserve_months < 1:
        risk_score += 35
    elif reserve_months < 3:
        risk_score += 20
    if financing_analysis:
        risk_score += {"seguro": 0, "moderado": 15, "arriscado": 35}.get(financing_analysis.get("classificacao"), 20)
    if investment_advice:
        rec = investment_advice.get("recomendacao")
        if rec == "priorizar_caixa_e_dividas":
            risk_score += 25
        elif rec == "construir_reserva":
            risk_score += 10
    classification = _class_from_score(risk_score)

    priority = build_priority_engine(
        income=income,
        expenses=expenses,
        emergency_reserve=emergency_reserve,
        reserve_months_target=float(profile.get("reserva_meses_alvo") or 6),
        monthly_payment=monthly_payment,
        investment_target=investment_target,
        risk_profile=str(profile.get("perfil_risco") or "conservador"),
    )
    projection = build_future_projection(
        income=income,
        expenses=expenses,
        emergency_reserve=emergency_reserve,
        monthly_payment=monthly_payment,
        planned_monthly_investment=investment_target,
        reserve_target=reserve_target,
    )
    plan = build_automatic_plan(priority=priority, classification=classification, profile=profile, projection=projection)
    alerts = build_smart_alerts({
        "classificacao": classification,
        "saldo_mensal": _round(income - expenses - monthly_payment),
        "comprometimento_pct": commitment,
        "meses_reserva": reserve_months,
    }, history)

    diagnosis_parts = [priority["problema_mais_critico"]["explicacao"]]
    if financing_analysis:
        diagnosis_parts.append(f"O financiamento analisado pesa {_money(monthly_payment)} por mês e muda sua capacidade de investir.")
    if investment_advice:
        diagnosis_parts.append(investment_advice.get("mensagem", ""))

    return {
        "decisao": DECISION_LABELS[classification],
        "classificacao": classification,
        "acao_principal_recomendada": priority["acao_principal_recomendada"],
        "diagnostico": " ".join(part for part in diagnosis_parts if part),
        "explicacao": {
            "por_que": priority["problema_mais_critico"]["explicacao"],
            "fatores_que_pesaram": [item["titulo"] for item in priority["ranking_problemas"][:4]],
            "o_que_esta_errado": priority["problema_mais_critico"]["titulo"],
            "como_melhorar": priority["acao_principal_recomendada"],
        },
        "motor_prioridade": priority,
        "projecao_futura": projection,
        "plano_automatico": plan,
        "alertas_inteligentes": alerts,
        "integracao_total": {
            "financiamento_impacta_investimento": monthly_payment > 0,
            "parcela_considerada": monthly_payment,
            "capacidade_investimento_apos_parcela": max(0.0, _round(income - expenses - monthly_payment)),
            "investimento_impacta_risco": investment_target > 0,
            "meta_investimento_considerada": investment_target,
            "mensagem": "O FinanceOS avaliou financiamento, reserva, metas e investimento como uma única decisão financeira.",
        },
    }

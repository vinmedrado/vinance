from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from backend.app.erp.models import ERPBudget, ERPExpense, ERPIncome, ERPPlannedInvestment
from backend.app.financial.models import FinancialGoal

BUDGET_MODELS = {
    "50_30_20": (50.0, 30.0, 20.0),
    "70_20_10": (70.0, 20.0, 10.0),
    "60_30_10": (60.0, 30.0, 10.0),
    "base_zero": (100.0, 0.0, 0.0),
    "custom": (50.0, 30.0, 20.0),
}


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def apply_budget_model(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    if model != "custom" and model in BUDGET_MODELS:
        n, w, i = BUDGET_MODELS[model]
        payload["needs_pct"], payload["wants_pct"], payload["investments_pct"] = n, w, i
    else:
        payload.setdefault("needs_pct", 50.0)
        payload.setdefault("wants_pct", 30.0)
        payload.setdefault("investments_pct", 20.0)
    return payload


def _scope_filter(model, tenant_key):
    if isinstance(tenant_key, str) and not tenant_key.isdigit() and hasattr(model, "organization_id"):
        return model.organization_id == tenant_key
    return model.user_id == tenant_key


def _scope_kwargs(tenant_key):
    if isinstance(tenant_key, str) and not tenant_key.isdigit():
        return {"organization_id": tenant_key}
    return {"user_id": tenant_key}


def get_or_create_budget(db: Session, user_id: int | str, year: int, month: int) -> ERPBudget:
    budget = db.query(ERPBudget).filter(_scope_filter(ERPBudget, user_id), ERPBudget.year == year, ERPBudget.month == month).first()
    if budget:
        return budget
    income = total_income(db, user_id, year, month)
    budget = ERPBudget(**_scope_kwargs(user_id), year=year, month=month, monthly_income=income, model="50_30_20")
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def total_income(db: Session, user_id: int | str, year: int, month: int) -> float:
    return float(db.query(func.coalesce(func.sum(ERPIncome.amount), 0)).filter(
        _scope_filter(ERPIncome, user_id),
        ERPIncome.deleted_at.is_(None),
        extract("year", ERPIncome.received_at) == year,
        extract("month", ERPIncome.received_at) == month,
    ).scalar() or 0)


def total_expenses(db: Session, user_id: int | str, year: int, month: int) -> float:
    return float(db.query(func.coalesce(func.sum(ERPExpense.amount), 0)).filter(
        _scope_filter(ERPExpense, user_id),
        ERPExpense.deleted_at.is_(None),
        extract("year", ERPExpense.due_date) == year,
        extract("month", ERPExpense.due_date) == month,
    ).scalar() or 0)


def category_breakdown(db: Session, user_id: int | str, year: int, month: int) -> list[dict[str, Any]]:
    rows = db.query(ERPExpense.category, func.coalesce(func.sum(ERPExpense.amount), 0)).filter(
        _scope_filter(ERPExpense, user_id),
        ERPExpense.deleted_at.is_(None),
        extract("year", ERPExpense.due_date) == year,
        extract("month", ERPExpense.due_date) == month,
    ).group_by(ERPExpense.category).all()
    return [{"name": name or "Sem categoria", "value": float(value or 0)} for name, value in rows]


def monthly_evolution(db: Session, user_id: int | str) -> list[dict[str, Any]]:
    today = date.today()
    data = []
    for offset in range(5, -1, -1):
        m = today.month - offset
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        data.append({"month": f"{m:02d}/{y}", "receitas": total_income(db, user_id, y, m), "despesas": total_expenses(db, user_id, y, m)})
    return data



# -----------------------------
# Vinance Intelligent Allocation Engine
# -----------------------------

CATEGORY_GROUPS = {
    "needs": {"moradia", "aluguel", "condominio", "condomínio", "mercado", "supermercado", "alimentação", "alimentacao", "transporte", "saúde", "saude", "educação", "educacao", "contas", "luz", "água", "agua", "internet", "telefone", "farmácia", "farmacia", "seguro", "imposto", "financiamento"},
    "wants": {"lazer", "delivery", "restaurante", "assinaturas", "streaming", "viagem", "compras", "roupas", "beleza", "academia", "hobby", "presente"},
    "investment": {"investimento", "investimentos", "reserva", "tesouro", "cdb", "ações", "acoes", "etf", "fiis", "fii", "bdr", "crypto", "cripto"},
}


def _norm_category(value: str | None) -> str:
    return (value or "").strip().lower()


def classify_expense_group(category: str | None, subcategory: str | None = None, description: str | None = None) -> str:
    blob = " ".join([_norm_category(category), _norm_category(subcategory), _norm_category(description)])
    for group, keys in CATEGORY_GROUPS.items():
        if any(k in blob for k in keys):
            return group
    return "needs"


def expense_groups_breakdown(db: Session, user_id: int | str, year: int, month: int) -> dict[str, float]:
    rows = db.query(ERPExpense).filter(
        _scope_filter(ERPExpense, user_id),
        ERPExpense.deleted_at.is_(None),
        extract("year", ERPExpense.due_date) == year,
        extract("month", ERPExpense.due_date) == month,
    ).all()
    out = {"needs": 0.0, "wants": 0.0, "investment": 0.0}
    for row in rows:
        group = classify_expense_group(row.category, row.subcategory, row.description)
        out[group] = out.get(group, 0.0) + float(row.amount or 0)
    return {k: round(v, 2) for k, v in out.items()}


def choose_budget_method(income: float, expenses: float, groups: dict[str, float]) -> dict[str, Any]:
    if income <= 0:
        return {"id": "aguardando_receita", "name": "Cadastre sua receita", "needs_pct": 0, "wants_pct": 0, "investments_pct": 0, "reason": "A renda mensal é necessária para calcular o método ideal."}
    expense_ratio = expenses / income
    needs_ratio = groups.get("needs", 0) / income
    if expense_ratio >= 0.92:
        return {"id": "recovery", "name": "Modo Recuperação", "needs_pct": 85, "wants_pct": 10, "investments_pct": 5, "reason": "As despesas consomem quase toda a renda. O foco é recuperar caixa antes de buscar risco."}
    if expense_ratio >= 0.72 or needs_ratio >= 0.65:
        return {"id": "70_20_10", "name": "70/20/10", "needs_pct": 70, "wants_pct": 20, "investments_pct": 10, "reason": "Seu orçamento está pressionado. O método prioriza estabilidade e reserva sem travar evolução."}
    if expense_ratio >= 0.58:
        return {"id": "60_30_10", "name": "60/30/10", "needs_pct": 60, "wants_pct": 30, "investments_pct": 10, "reason": "Existe sobra, mas ainda é melhor fortalecer caixa antes de acelerar investimentos."}
    return {"id": "50_30_20", "name": "50/30/20", "needs_pct": 50, "wants_pct": 30, "investments_pct": 20, "reason": "A relação renda/despesa permite uma distribuição equilibrada entre vida atual e construção patrimonial."}


def infer_risk_profile(income: float, expenses: float, balance: float, emergency_gap: float) -> str:
    if income <= 0 or balance <= 0:
        return "defensivo"
    free_ratio = balance / income
    expense_ratio = expenses / income
    if emergency_gap > balance * 6 or expense_ratio > 0.75:
        return "conservador"
    if free_ratio >= 0.35 and expense_ratio <= 0.55:
        return "arrojado"
    return "moderado"


def build_market_recommendations(profile: str, investable: float, emergency_gap: float) -> list[dict[str, Any]]:
    if investable <= 0:
        return []
    if emergency_gap > 0:
        template = [
            ("Tesouro Selic", "Renda fixa pública", 45, "baixo", "liquidez e segurança para formar reserva"),
            ("CDB liquidez diária", "Renda fixa bancária", 35, "baixo", "caixa remunerado para emergências"),
            ("ETF amplo", "ETF", 20, "médio", "pequena diversificação sem comprometer liquidez"),
        ]
    elif profile in {"defensivo", "conservador"}:
        template = [
            ("Tesouro Selic", "Renda fixa pública", 35, "baixo", "proteção de caixa e liquidez"),
            ("CDB/LCI/LCA", "Renda fixa", 35, "baixo", "previsibilidade e baixo risco"),
            ("ETF amplo", "ETF", 20, "médio", "diversificação gradual"),
            ("FIIs de qualidade", "FIIs", 10, "médio", "renda recorrente com exposição controlada"),
        ]
    elif profile == "moderado":
        template = [
            ("Tesouro IPCA", "Renda fixa inflação", 25, "baixo-médio", "proteção de poder de compra"),
            ("ETFs Brasil/Exterior", "ETF", 35, "médio", "diversificação simples entre mercados"),
            ("FIIs", "Fundos imobiliários", 20, "médio", "renda recorrente e diversificação"),
            ("Ações líderes", "Ações", 15, "médio-alto", "crescimento patrimonial controlado"),
            ("BDRs/ETF internacional", "Exterior", 5, "médio-alto", "exposição global limitada"),
        ]
    else:
        template = [
            ("ETFs globais", "ETF internacional", 30, "médio", "base diversificada para crescimento"),
            ("Ações", "Renda variável", 25, "alto", "maior potencial de retorno com oscilação"),
            ("FIIs", "Fundos imobiliários", 15, "médio", "renda recorrente"),
            ("Tesouro IPCA/CDB", "Renda fixa", 20, "baixo-médio", "contrapeso de estabilidade"),
            ("BDRs", "Exterior", 7, "alto", "diversificação internacional"),
            ("Cripto", "Alternativos", 3, "muito alto", "exposição pequena e controlada"),
        ]
    return [
        {"name": name, "market": market, "allocation_pct": pct, "amount": round(investable * pct / 100, 2), "risk": risk, "reason": reason}
        for name, market, pct, risk, reason in template
    ]


def build_intelligent_allocation(db: Session, user_id: int | str, year: int, month: int, income: float, expenses: float, realized_investment: float) -> dict[str, Any]:
    groups = expense_groups_breakdown(db, user_id, year, month)
    balance = round(income - expenses, 2)
    method = choose_budget_method(income, expenses, groups)
    emergency_target = round(max(expenses, 0) * 6, 2)
    # Sem campo dedicado de reserva nesta tela, usa investimentos realizados como proxy conservadora.
    current_reserve_proxy = max(realized_investment, 0)
    emergency_gap = round(max(emergency_target - current_reserve_proxy, 0), 2)
    if income <= 0 or balance <= 0:
        investable = 0.0
    else:
        method_target = income * (method.get("investments_pct", 0) / 100)
        # Se ainda há reserva a construir, evita recomendar todo o saldo para risco.
        reserve_floor = min(balance, max(0, balance * 0.30)) if emergency_gap > 0 else 0
        investable = max(0.0, min(balance - reserve_floor, method_target if method_target > 0 else balance * 0.20))
        if method["id"] == "recovery":
            investable = min(investable, balance * 0.10)
    investable = round(investable, 2)
    risk_profile = infer_risk_profile(income, expenses, balance, emergency_gap)
    markets = build_market_recommendations(risk_profile, investable, emergency_gap)
    can_invest = investable > 0
    if not can_invest:
        decision = "Ainda não é recomendado investir agora."
        next_action = "Priorize cadastrar todas as despesas, reduzir custos variáveis e recuperar saldo positivo."
    elif emergency_gap > 0:
        decision = f"Você pode começar investindo R$ {investable:,.2f}/mês, priorizando reserva e liquidez."
        next_action = "Forme reserva antes de aumentar renda variável."
    else:
        decision = f"Você pode investir R$ {investable:,.2f}/mês com perfil {risk_profile}."
        next_action = "Distribua o aporte conforme os mercados sugeridos e revise mensalmente."
    return {
        "can_invest": can_invest,
        "decision": decision.replace(',', 'X').replace('.', ',').replace('X', '.'),
        "next_action": next_action,
        "method": method,
        "risk_profile": risk_profile,
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "balance": balance,
        "expense_ratio_pct": round((expenses / income * 100) if income else 0, 2),
        "investable_amount": investable,
        "emergency_reserve_target": emergency_target,
        "emergency_reserve_gap": emergency_gap,
        "groups": groups,
        "markets": markets,
        "advisor_notes": [
            method["reason"],
            "O valor recomendado considera renda, despesas do mês, orçamento e necessidade de reserva.",
            "A alocação sugerida é educativa e deve ser revisada antes de qualquer decisão real de investimento.",
        ],
    }

def build_dashboard(db: Session, user_id: int | str, year: int | None = None, month: int | None = None) -> dict[str, Any]:
    today = date.today()
    year = year or today.year
    month = month or today.month
    income = total_income(db, user_id, year, month)
    expenses = total_expenses(db, user_id, year, month)
    budget = get_or_create_budget(db, user_id, year, month)
    planned_investment = float(db.query(func.coalesce(func.sum(ERPPlannedInvestment.planned_amount), 0)).filter(_scope_filter(ERPPlannedInvestment, user_id), ERPPlannedInvestment.year == year, ERPPlannedInvestment.month == month).scalar() or 0)
    realized_investment = float(db.query(func.coalesce(func.sum(ERPPlannedInvestment.realized_amount), 0)).filter(_scope_filter(ERPPlannedInvestment, user_id), ERPPlannedInvestment.year == year, ERPPlannedInvestment.month == month).scalar() or 0)
    investment_target = income * (budget.investments_pct / 100) if income else budget.monthly_income * (budget.investments_pct / 100)
    balance = income - expenses
    invested_pct = (realized_investment / income * 100) if income else 0
    budget_used = (expenses / max(income, budget.monthly_income, 1)) * 100
    alerts = generate_alerts(income, expenses, budget, realized_investment)
    intelligence = build_intelligent_allocation(db, user_id, year, month, income, expenses, realized_investment)
    return {
        "period": {"year": year, "month": month},
        "metrics": {
            "monthly_balance": round(balance, 2),
            "total_income": round(income, 2),
            "total_expenses": round(expenses, 2),
            "available_to_invest": round(max(balance, 0), 2),
            "invested_pct": round(invested_pct, 2),
            "recommended_investment": round(investment_target, 2),
            "planned_investment": round(planned_investment, 2),
            "realized_investment": round(realized_investment, 2),
            "budget_used_pct": round(budget_used, 2),
            "financial_score": financial_score(income, expenses, realized_investment, investment_target),
        },
        "budget": budget_payload(budget, income, expenses, realized_investment),
        "charts": {"by_category": category_breakdown(db, user_id, year, month), "evolution": monthly_evolution(db, user_id)},
        "recommendation": main_recommendation(income, expenses, investment_target, realized_investment),
        "alerts": alerts,
        "intelligent_allocation": intelligence,
    }


def budget_payload(budget: ERPBudget, income: float, expenses: float, invested: float) -> dict[str, Any]:
    base = income or budget.monthly_income
    return {
        "model": budget.model,
        "monthly_income": base,
        "limits": {
            "needs": round(base * budget.needs_pct / 100, 2),
            "wants": round(base * budget.wants_pct / 100, 2),
            "investments": round(base * budget.investments_pct / 100, 2),
        },
        "actual": {"expenses": expenses, "investments": invested},
        "difference": {"expenses": round(base - expenses, 2), "investments": round(invested - (base * budget.investments_pct / 100), 2)},
    }


def financial_score(income: float, expenses: float, invested: float, target: float) -> int:
    if income <= 0:
        return 35
    expense_ratio = expenses / income
    invest_ratio = (invested / target) if target else 0
    score = 100 - max(0, (expense_ratio - 0.70) * 100) - max(0, (0.15 - (invested / income)) * 80)
    score += min(10, invest_ratio * 5)
    return int(max(0, min(100, score)))


def generate_alerts(income: float, expenses: float, budget: ERPBudget, invested: float) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if income <= 0:
        alerts.append({"severity": "warning", "title": "Cadastre sua renda", "message": "Com a renda mensal, o FinanceOS calcula orçamento e investimento ideal."})
        return alerts
    if expenses > income * 0.85:
        alerts.append({"severity": "danger", "title": "Gastos muito altos", "message": "Suas despesas passaram de 85% da renda mensal."})
    target = income * budget.investments_pct / 100
    if invested < target:
        alerts.append({"severity": "info", "title": "Investimento abaixo do plano", "message": f"Faltam R$ {target - invested:,.2f} para atingir o modelo escolhido."})
    if not alerts:
        alerts.append({"severity": "success", "title": "Mês sob controle", "message": "Seu orçamento está dentro de uma faixa saudável."})
    return alerts


def main_recommendation(income: float, expenses: float, target: float, invested: float) -> dict[str, str | float]:
    balance = income - expenses
    if income <= 0:
        return {"title": "Comece cadastrando receitas", "message": "A renda mensal libera diagnóstico, orçamento e sugestão de investimento.", "amount": 0}
    if balance <= 0:
        return {"title": "Priorize reduzir despesas", "message": "Antes de investir, ajuste categorias que estão pressionando seu caixa.", "amount": 0}
    missing = max(target - invested, 0)
    return {"title": "Valor sugerido para investir", "message": "Baseado no orçamento escolhido e no saldo atual do mês.", "amount": round(min(balance, missing or balance), 2)}


def build_diagnosis(db: Session, user_id: int | str, year: int | None = None, month: int | None = None) -> dict[str, Any]:
    dashboard = build_dashboard(db, user_id, year, month)
    score = int(dashboard["metrics"]["financial_score"])
    status = "excelente" if score >= 85 else "bom" if score >= 70 else "atenção" if score >= 50 else "crítico"
    recommendations = [dashboard["recommendation"]]
    if dashboard["metrics"]["budget_used_pct"] > 85:
        recommendations.append({"title": "Revise despesas variáveis", "message": "Filtre gastos por categoria e reduza o que não é essencial neste mês.", "amount": 0})
    return {
        "score": score,
        "status": status,
        "alerts": dashboard["alerts"],
        "recommendations": recommendations,
        "forecast": {
            "expected_close": round(dashboard["metrics"]["monthly_balance"], 2),
            "confidence": "média",
            "message": "Previsão baseada nas receitas, despesas e recorrências cadastradas.",
        },
        "investment_connection": {
            "recommended_monthly_amount": dashboard["metrics"]["recommended_investment"],
            "available_now": dashboard["metrics"]["available_to_invest"],
            "difference_vs_plan": round(dashboard["metrics"]["realized_investment"] - dashboard["metrics"]["recommended_investment"], 2),
            "message": "O orçamento define quanto deveria ir para investimento antes da análise de carteira.",
        },
    }

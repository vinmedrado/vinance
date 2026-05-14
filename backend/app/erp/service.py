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
        extract("year", ERPIncome.received_at) == year,
        extract("month", ERPIncome.received_at) == month,
    ).scalar() or 0)


def total_expenses(db: Session, user_id: int | str, year: int, month: int) -> float:
    return float(db.query(func.coalesce(func.sum(ERPExpense.amount), 0)).filter(
        _scope_filter(ERPExpense, user_id),
        extract("year", ERPExpense.due_date) == year,
        extract("month", ERPExpense.due_date) == month,
    ).scalar() or 0)


def category_breakdown(db: Session, user_id: int | str, year: int, month: int) -> list[dict[str, Any]]:
    rows = db.query(ERPExpense.category, func.coalesce(func.sum(ERPExpense.amount), 0)).filter(
        _scope_filter(ERPExpense, user_id),
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

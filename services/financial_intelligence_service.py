from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from services.financial_crud_service import calculate_budget, money, month_ref, summarize_month


def calculate_financial_score(summary: Dict[str, Any], budget_rows: List[Dict[str, Any]]) -> int:
    income = float(summary.get("income_base") or summary.get("income") or 0)
    expenses = float(summary.get("expenses") or 0)
    invested = float(summary.get("invested") or 0)
    overdue = float(summary.get("overdue") or 0)
    pending = float(summary.get("pending") or 0)
    score = 100
    if income <= 0:
        score -= 25
    if income and expenses > income * 0.8:
        score -= 20
    if overdue > 0:
        score -= 18
    if pending > income * 0.20 and income:
        score -= 8
    invest_target = float(summary.get("recommended_investment") or 0)
    if invest_target and invested < invest_target * 0.65:
        score -= 15
    for row in budget_rows:
        if row.get("Diferença", 0) < 0:
            score -= 7
    return max(0, min(100, int(score)))


def detect_categories_above_limit(budget_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in budget_rows if float(row.get("Diferença") or 0) < 0]


def forecast_month_close(summary: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    day = max(today.day, 1)
    projected_expenses = float(summary.get("expenses") or 0) / day * 30
    projected_invested = float(summary.get("invested") or 0)
    projected_balance = float(summary.get("income") or summary.get("income_base") or 0) - projected_expenses - projected_invested
    return {
        "projected_expenses": projected_expenses,
        "projected_balance": projected_balance,
        "message": f"Mantendo o ritmo atual, o fechamento estimado fica em despesas de {money(projected_expenses)} e saldo de {money(projected_balance)}.",
    }


def suggest_savings(summary: Dict[str, Any], above_limits: List[Dict[str, Any]]) -> List[str]:
    suggestions: list[str] = []
    if above_limits:
        for row in above_limits[:3]:
            suggestions.append(f"Reduzir {money(abs(float(row['Diferença'])))} em {row['Categoria']} para voltar ao plano.")
    if float(summary.get("pending") or 0) > 0:
        suggestions.append(f"Resolver pendências de {money(summary['pending'])} antes do fechamento do mês.")
    if float(summary.get("investment_gap") or 0) < 0:
        suggestions.append(f"Ajustar gastos para liberar {money(abs(summary['investment_gap']))} e alcançar a meta de investimento.")
    if not suggestions:
        suggestions.append("Manter o ritmo atual e revisar oportunidades de investimento com cautela.")
    return suggestions


def suggest_monthly_investment(summary: Dict[str, Any]) -> Dict[str, Any]:
    target = float(summary.get("recommended_investment") or 0)
    available = float(summary.get("available_to_invest") or 0)
    suggested = min(target, available) if target else available
    return {
        "target": target,
        "available": available,
        "suggested": max(suggested, 0),
        "message": f"Valor sugerido para investir neste mês: {money(max(suggested, 0))}, respeitando orçamento e sobra disponível.",
    }


def build_financial_diagnosis(user_id: str = "demo-user", month: str | None = None) -> Dict[str, Any]:
    month = month or month_ref()
    summary = summarize_month(user_id=user_id, month=month)
    budget_rows = calculate_budget(summary.get("budget_model", "50/30/20"), summary.get("income_base", 0), summary.get("by_category", {}))
    above = detect_categories_above_limit(budget_rows)
    forecast = forecast_month_close(summary)
    invest = suggest_monthly_investment(summary)
    score = calculate_financial_score(summary, budget_rows)
    label = "Excelente" if score >= 85 else "Saudável" if score >= 70 else "Atenção" if score >= 50 else "Crítico"
    alerts = []
    if above:
        alerts.append(f"{len(above)} categoria(s) acima do limite do orçamento.")
    if summary.get("overdue", 0) > 0:
        alerts.append(f"Existem despesas vencidas somando {money(summary['overdue'])}.")
    if summary.get("investment_gap", 0) < 0:
        alerts.append(f"Falta {money(abs(summary['investment_gap']))} para atingir a meta mensal de investimento.")
    if not alerts:
        alerts.append("Nenhum alerta crítico no momento.")
    return {
        "summary": summary,
        "budget_rows": budget_rows,
        "score": score,
        "label": label,
        "alerts": alerts,
        "above_limits": above,
        "forecast": forecast,
        "investment": invest,
        "savings_suggestions": suggest_savings(summary, above),
    }

from __future__ import annotations

from typing import Any

from services.financial_crud_service import (
    BUDGET_MODELS,
    calculate_budget,
    money,
    summarize_month,
    seed_demo_if_empty,
)


def summarize_expenses(expenses: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if expenses is not None:
        total = sum(float(r.get('valor') or r.get('amount') or 0) for r in expenses)
        pending = sum(float(r.get('valor') or r.get('amount') or 0) for r in expenses if str(r.get('status')).lower() == 'pendente')
        paid = sum(float(r.get('valor') or r.get('amount') or 0) for r in expenses if str(r.get('status')).lower() in {'pago','recebido'})
        overdue = sum(float(r.get('valor') or r.get('amount') or 0) for r in expenses if str(r.get('status')).lower() == 'vencido')
        by_cat: dict[str, float] = {}
        for r in expenses:
            key = str(r.get('categoria') or r.get('category') or 'Outros')
            by_cat[key] = by_cat.get(key, 0.0) + float(r.get('valor') or r.get('amount') or 0)
        biggest = max(by_cat.items(), key=lambda x: x[1])[0] if by_cat else '-'
        return {'total': total, 'pending': pending, 'paid': paid, 'overdue': overdue, 'biggest_category': biggest, 'invested': by_cat.get('Investimentos/Reserva',0.0), 'by_category': by_cat, 'rows': expenses}
    data = summarize_month()
    return {'total': data['expenses'] + data['invested'], 'pending': data['pending'], 'paid': 0, 'overdue': data['overdue'], 'biggest_category': data['biggest_category'], 'invested': data['invested'], 'by_category': data['by_category'], 'rows': data['rows']}

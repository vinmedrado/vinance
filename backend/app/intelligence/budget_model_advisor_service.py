from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BudgetAdvisorInput:
    monthly_income: float
    total_expenses: float
    fixed_expenses: float = 0.0
    variable_expenses: float = 0.0
    debt_payments: float = 0.0
    overdue_bills: float = 0.0
    available_balance: float = 0.0
    emergency_reserve: float = 0.0
    savings_rate: float = 0.0
    expense_ratio: float = 0.0
    debt_ratio: float = 0.0
    goal_priority: str | None = None
    risk_profile: str = "moderate"


class BudgetModelAdvisorService:
    """Motor central do fluxo renda -> despesas -> modelo ideal -> plano -> investimento.

    A saída é propositalmente humana. Métricas quantitativas ficam internas e são
    traduzidas para recomendações simples para a UX.
    """

    MODEL_LABELS = {
        "base_zero": "Base Zero",
        "70_20_10": "70/20/10",
        "60_30_10": "60/30/10",
        "50_30_20": "50/30/20",
        "custom_aggressive": "Personalizado para metas e investimentos",
        "recovery": "Recuperação financeira",
    }

    @staticmethod
    def _money(value: float) -> float:
        return round(max(float(value or 0), 0), 2)

    @classmethod
    def collect_from_erp(cls, db: "Session", organization_id: str, year: int | None = None, month: int | None = None) -> BudgetAdvisorInput:
        from sqlalchemy import extract, func
        from backend.app.erp.models import ERPAccount, ERPCard, ERPExpense, ERPIncome
        from backend.app.financial.models import FinancialGoal
        today = date.today()
        year = year or today.year
        month = month or today.month

        income = float(db.query(func.coalesce(func.sum(ERPIncome.amount), 0)).filter(
            ERPIncome.organization_id == organization_id,
            ERPIncome.deleted_at.is_(None),
            extract("year", ERPIncome.received_at) == year,
            extract("month", ERPIncome.received_at) == month,
        ).scalar() or 0)

        expenses_query = db.query(ERPExpense).filter(
            ERPExpense.organization_id == organization_id,
            ERPExpense.deleted_at.is_(None),
            extract("year", ERPExpense.due_date) == year,
            extract("month", ERPExpense.due_date) == month,
        )
        expenses = expenses_query.all()
        total_expenses = sum(float(e.amount or 0) for e in expenses)

        fixed_markers = {"fixed", "fixa", "fixo", "rent", "aluguel", "financiamento", "loan", "divida", "dívida"}
        debt_markers = {"debt", "loan", "cartao", "cartão", "divida", "dívida", "financiamento", "parcela", "atras"}
        fixed_expenses = 0.0
        variable_expenses = 0.0
        debt_payments = 0.0
        overdue_bills = 0.0
        for item in expenses:
            text = " ".join(str(x or "").lower() for x in [item.category, item.subcategory, item.description, item.tags, item.notes])
            amount = float(item.amount or 0)
            if item.recurrence and item.recurrence != "none" or any(marker in text for marker in fixed_markers):
                fixed_expenses += amount
            else:
                variable_expenses += amount
            if any(marker in text for marker in debt_markers):
                debt_payments += amount
            if item.status in {"overdue", "late", "atrasada", "atrasado"} or (item.due_date and item.due_date < today and item.status != "paid"):
                overdue_bills += amount

        # Usa limites cadastrados como um proxy conservador de passivos possíveis, sem assumir dívida real.
        card_limit = float(db.query(func.coalesce(func.sum(ERPCard.limit_amount), 0)).filter(
            ERPCard.organization_id == organization_id, ERPCard.deleted_at.is_(None), ERPCard.is_active.is_(True)
        ).scalar() or 0)
        account_balance = float(db.query(func.coalesce(func.sum(ERPAccount.initial_balance), 0)).filter(
            ERPAccount.organization_id == organization_id, ERPAccount.deleted_at.is_(None), ERPAccount.is_active.is_(True)
        ).scalar() or 0)
        emergency_reserve = max(account_balance, 0)
        available_balance = income - total_expenses
        expense_ratio = (total_expenses / income) if income > 0 else 1.0
        debt_ratio = (debt_payments / income) if income > 0 else 0.0
        savings_rate = (available_balance / income) if income > 0 else 0.0

        goal = db.query(FinancialGoal).filter(
            FinancialGoal.organization_id == organization_id,
            FinancialGoal.deleted_at.is_(None),
        ).order_by(FinancialGoal.created_at.desc()).first()

        return BudgetAdvisorInput(
            monthly_income=income,
            total_expenses=total_expenses,
            fixed_expenses=fixed_expenses,
            variable_expenses=variable_expenses,
            debt_payments=max(debt_payments, 0),
            overdue_bills=overdue_bills,
            available_balance=available_balance,
            emergency_reserve=emergency_reserve,
            savings_rate=savings_rate,
            expense_ratio=expense_ratio,
            debt_ratio=debt_ratio,
            goal_priority=getattr(goal, "name", None) or getattr(goal, "title", None) if goal else None,
            risk_profile="moderate",
        )

    @classmethod
    def recommend(cls, data: BudgetAdvisorInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = BudgetAdvisorInput(**data)
        income = max(float(data.monthly_income or 0), 0)
        expenses = max(float(data.total_expenses or 0), 0)
        debts = max(float(data.debt_payments or 0), 0)
        overdue = max(float(data.overdue_bills or 0), 0)
        balance = income - expenses
        ratio = ((expenses + debts) / income) if income > 0 else 1.0
        debt_ratio = (debts / income) if income > 0 else 0.0

        if income <= 0:
            model = "base_zero"
            confidence = 0.65
            phase = "cadastro_inicial"
            reason = "Ainda falta cadastrar sua renda para o Vinance montar um plano confiável."
        elif overdue > 0:
            model = "recovery"
            confidence = 0.94
            phase = "recuperacao_financeira"
            reason = "Existem contas atrasadas; o foco do mês deve ser recuperar controle antes de aumentar investimentos."
        elif ratio >= 0.85:
            model = "base_zero" if ratio >= 0.95 else "70_20_10"
            confidence = 0.91
            phase = "controle_e_eliminacao_de_contas"
            reason = f"Suas despesas e dívidas comprometem aproximadamente {ratio * 100:.0f}% da renda."
        elif ratio >= 0.70:
            model = "60_30_10"
            confidence = 0.86
            phase = "reorganizacao_financeira"
            reason = f"Você está com cerca de {ratio * 100:.0f}% da renda comprometida; ainda dá para reorganizar sem travar totalmente sua rotina."
        elif ratio >= 0.50:
            model = "50_30_20"
            confidence = 0.84
            phase = "equilibrio_e_investimento"
            reason = f"Seu comprometimento está em torno de {ratio * 100:.0f}% da renda, uma faixa boa para equilibrar vida, reserva e investimentos."
        else:
            model = "custom_aggressive"
            confidence = 0.82
            phase = "aceleracao_de_metas"
            reason = f"Suas despesas estão abaixo de 50% da renda; existe espaço para acelerar metas e investimentos com segurança."

        limits = cls._suggest_limits(model, income, expenses, debts, overdue, balance)
        investment_capacity = cls._safe_investment_capacity(model, income, expenses, debts, overdue, data.emergency_reserve)
        warnings = cls._warnings(income, ratio, debt_ratio, overdue, investment_capacity)
        action_plan = cls._action_plan(model, limits, investment_capacity, overdue, ratio)
        health_score = cls._health_score(income, ratio, debt_ratio, overdue, data.emergency_reserve)

        return {
            "recommended_model": model,
            "model_label": cls.MODEL_LABELS[model],
            "confidence_score": round(confidence, 2),
            "financial_phase": phase,
            "reason": reason,
            "action_plan": action_plan,
            "suggested_limits": limits,
            "warnings": warnings,
            "investment_capacity": investment_capacity,
            "health_score": health_score,
            "investment_gate": cls._investment_gate(model, investment_capacity, ratio, overdue),
            "input_summary": asdict(data),
            "disclaimer": "O Vinance fornece simulações e análises educacionais. Isso não constitui recomendação financeira.",
        }

    @classmethod
    def _suggest_limits(cls, model: str, income: float, expenses: float, debts: float, overdue: float, balance: float) -> dict[str, float]:
        if income <= 0:
            return {"needs": 0, "wants": 0, "debts": 0, "emergency_reserve": 0, "investments": 0}
        if model == "recovery":
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.70, 0.05, 0.20, 0.05, 0.00
        elif model == "base_zero":
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.75, 0.05, 0.15, 0.05, 0.00
        elif model == "70_20_10":
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.70, 0.15, 0.05, 0.05, 0.05
        elif model == "60_30_10":
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.60, 0.25, 0.05, 0.05, 0.05
        elif model == "50_30_20":
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.50, 0.25, 0.05, 0.05, 0.15
        else:
            needs_pct, wants_pct, debt_pct, reserve_pct, inv_pct = 0.45, 0.20, 0.00, 0.10, 0.25
        return {
            "needs": cls._money(income * needs_pct),
            "wants": cls._money(income * wants_pct),
            "debts": cls._money(max(income * debt_pct, overdue)),
            "emergency_reserve": cls._money(income * reserve_pct),
            "investments": cls._money(min(max(balance, 0), income * inv_pct)),
        }

    @classmethod
    def _safe_investment_capacity(cls, model: str, income: float, expenses: float, debts: float, overdue: float, emergency_reserve: float) -> float:
        if income <= 0 or overdue > 0:
            return 0.0
        surplus = max(income - expenses, 0)
        safety_buffer = max(income * 0.05, 100 if income > 0 else 0)
        reserve_gap = max((expenses * 3) - emergency_reserve, 0)
        reserve_priority = min(surplus * 0.5, reserve_gap / 6) if reserve_gap > 0 else 0
        raw_capacity = max(surplus - safety_buffer - reserve_priority, 0)
        cap_by_model = {
            "base_zero": 0.02,
            "70_20_10": 0.05,
            "60_30_10": 0.08,
            "50_30_20": 0.18,
            "custom_aggressive": 0.30,
            "recovery": 0.0,
        }.get(model, 0.10) * income
        return cls._money(min(raw_capacity, cap_by_model))

    @staticmethod
    def _health_score(income: float, ratio: float, debt_ratio: float, overdue: float, emergency_reserve: float) -> int:
        if income <= 0:
            return 25
        score = 100
        score -= max(0, (ratio - 0.50) * 120)
        score -= max(0, debt_ratio * 80)
        if overdue > 0:
            score -= 25
        if emergency_reserve < income:
            score -= 8
        return int(max(0, min(100, round(score))))

    @staticmethod
    def _warnings(income: float, ratio: float, debt_ratio: float, overdue: float, investment_capacity: float) -> list[str]:
        warnings: list[str] = []
        if income <= 0:
            warnings.append("Cadastre sua renda para receber uma recomendação completa.")
        if overdue > 0:
            warnings.append("Priorize contas atrasadas antes de aumentar aportes em investimentos.")
        if ratio >= 0.85:
            warnings.append("Sua renda está muito comprometida; evite novas parcelas neste mês.")
        if debt_ratio >= 0.20:
            warnings.append("As dívidas estão pesando no orçamento; revise juros e vencimentos.")
        if investment_capacity <= 0 and income > 0:
            warnings.append("Neste momento, o valor seguro para investir é baixo. Foque em caixa e organização.")
        return warnings

    @staticmethod
    def _action_plan(model: str, limits: dict[str, float], investment_capacity: float, overdue: float, ratio: float) -> list[str]:
        if model == "recovery":
            return [
                f"Priorizar R$ {limits['debts']:.2f} para contas atrasadas e dívidas essenciais.",
                f"Limitar desejos/lazer a aproximadamente R$ {limits['wants']:.2f} neste mês.",
                "Evitar novas compras parceladas até regularizar os atrasos.",
                "Investir somente após estabilizar o caixa do mês.",
            ]
        if model in {"base_zero", "70_20_10"}:
            return [
                "Dar destino para cada real da renda antes do mês começar.",
                f"Manter necessidades até R$ {limits['needs']:.2f} e cortar gastos variáveis primeiro.",
                f"Separar R$ {limits['emergency_reserve']:.2f} para reserva se o caixa permitir.",
                f"Investir no máximo R$ {investment_capacity:.2f} com margem de segurança.",
            ]
        if model == "60_30_10":
            return [
                "Reorganizar despesas sem zerar qualidade de vida.",
                f"Travar desejos/lazer perto de R$ {limits['wants']:.2f}.",
                f"Reservar até R$ {limits['emergency_reserve']:.2f} para proteção de caixa.",
                f"Usar R$ {investment_capacity:.2f} como aporte seguro estimado.",
            ]
        if model == "50_30_20":
            return [
                "Manter equilíbrio entre necessidades, escolhas pessoais e futuro.",
                f"Planejar investimento mensal seguro de aproximadamente R$ {investment_capacity:.2f}.",
                "Conectar metas e investimentos para simular crescimento com ML/backtest.",
            ]
        return [
            "Acelerar metas sem perder reserva de segurança.",
            f"Direcionar aproximadamente R$ {investment_capacity:.2f} para investimentos/metas neste mês.",
            "Usar o motor de investimentos para comparar cenários antes de aumentar risco.",
        ]

    @staticmethod
    def _investment_gate(model: str, investment_capacity: float, ratio: float, overdue: float) -> dict[str, Any]:
        if overdue > 0 or model == "recovery":
            return {"status": "blocked", "message": "Antes de investir mais, o ideal é regularizar contas atrasadas e recuperar caixa.", "safe_amount": 0.0}
        if investment_capacity <= 0 or ratio >= 0.85:
            return {"status": "organize_first", "message": "Antes de investir mais, reduza o comprometimento da renda e crie margem de segurança.", "safe_amount": 0.0}
        if ratio >= 0.70:
            return {"status": "conservative", "message": f"Você possui margem limitada. O valor seguro estimado para investir é R$ {investment_capacity:.2f} neste mês.", "safe_amount": investment_capacity}
        return {"status": "enabled", "message": f"Você possui margem segura para investir aproximadamente R$ {investment_capacity:.2f} neste mês.", "safe_amount": investment_capacity}

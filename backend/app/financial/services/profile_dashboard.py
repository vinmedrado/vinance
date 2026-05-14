from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.financial.models import (
    FinancialDecisionHistory,
    FinancialGoal,
    FinancialMonthlyReport,
    FinancialUserProfile,
    MonthlyFinancialTarget,
)
from backend.app.financial.services.financial_analysis import get_financial_summary


def _classify(commitment: float | None, reserve_months: float, balance: float, income: float) -> tuple[str, str]:
    balance_ratio = balance / income if income > 0 else 0
    if income <= 0:
        return "arriscado", "Cadastre sua renda mensal para o FinanceOS calcular sua saúde financeira real."
    if balance < 0 or (commitment is not None and commitment > 0.75):
        return "arriscado", "Seu orçamento está pressionado: despesas consomem grande parte da renda e reduzem sua margem de segurança."
    if reserve_months >= 6 and balance_ratio >= 0.20 and (commitment is None or commitment <= 0.60):
        return "seguro", "Sua base financeira está saudável: existe sobra mensal e reserva próxima do nível recomendado."
    if reserve_months >= 3 and balance_ratio > 0:
        return "moderado", "Você tem alguma margem, mas ainda precisa fortalecer reserva e controlar novas parcelas."
    return "arriscado", "A principal fragilidade está na baixa reserva de emergência e/ou pouca sobra mensal."


def ensure_profile(db: Session, user_id: int) -> FinancialUserProfile:
    profile = db.query(FinancialUserProfile).filter(FinancialUserProfile.user_id == user_id).one_or_none()
    if profile:
        return profile
    profile = FinancialUserProfile(user_id=user_id, onboarding_completed=False)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def upsert_profile(db: Session, user_id: int, payload: dict[str, Any]) -> FinancialUserProfile:
    profile = ensure_profile(db, user_id)
    for key, value in payload.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def profile_to_dict(profile: FinancialUserProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "nome": profile.nome,
        "perfil_risco": profile.perfil_risco,
        "renda_mensal": profile.renda_mensal,
        "despesas_mensais": profile.despesas_mensais,
        "reserva_emergencia": profile.reserva_emergencia,
        "reserva_meses_alvo": profile.reserva_meses_alvo,
        "meta_investimento_mensal": profile.meta_investimento_mensal,
        "meta_economia_mensal": profile.meta_economia_mensal,
        "objetivo_principal": profile.objetivo_principal,
        "onboarding_completed": profile.onboarding_completed,
    }


def create_goal(db: Session, user_id: int, payload: dict[str, Any]) -> FinancialGoal:
    goal = FinancialGoal(user_id=user_id, **payload)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def goal_to_dict(goal: FinancialGoal) -> dict[str, Any]:
    progresso = (goal.valor_atual / goal.valor_alvo) if goal.valor_alvo > 0 else 0
    return {
        "id": goal.id,
        "nome": goal.nome,
        "tipo": goal.tipo,
        "valor_alvo": goal.valor_alvo,
        "valor_atual": goal.valor_atual,
        "prazo": goal.prazo.isoformat() if goal.prazo else None,
        "prioridade": goal.prioridade,
        "status": goal.status,
        "progresso_pct": round(min(max(progresso, 0), 1), 6),
    }


def upsert_monthly_target(db: Session, user_id: int, payload: dict[str, Any]) -> MonthlyFinancialTarget:
    target = (
        db.query(MonthlyFinancialTarget)
        .filter(
            MonthlyFinancialTarget.user_id == user_id,
            MonthlyFinancialTarget.year == payload["year"],
            MonthlyFinancialTarget.month == payload["month"],
        )
        .one_or_none()
    )
    if target is None:
        target = MonthlyFinancialTarget(user_id=user_id, **payload)
        db.add(target)
    else:
        for key, value in payload.items():
            setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


def target_to_dict(target: MonthlyFinancialTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "year": target.year,
        "month": target.month,
        "renda_prevista": target.renda_prevista,
        "despesa_limite": target.despesa_limite,
        "economia_meta": target.economia_meta,
        "investimento_meta": target.investimento_meta,
        "reserva_meta": target.reserva_meta,
        "observacao": target.observacao,
        "saldo_planejado": target.renda_prevista - target.despesa_limite,
    }


def build_executive_dashboard(db: Session, user_id: int) -> dict[str, Any]:
    profile = ensure_profile(db, user_id)
    core = get_financial_summary()

    income = profile.renda_mensal or core.get("renda_total", 0.0)
    expenses = profile.despesas_mensais or core.get("despesas_totais", 0.0)
    balance = income - expenses
    commitment = expenses / income if income > 0 else None
    reserve_target = expenses * profile.reserva_meses_alvo
    reserve_gap = max(reserve_target - profile.reserva_emergencia, 0)
    reserve_months = profile.reserva_emergencia / expenses if expenses > 0 else 0
    classification, diagnosis = _classify(commitment, reserve_months, balance, income)

    today = date.today()
    goals = (
        db.query(FinancialGoal)
        .filter(FinancialGoal.user_id == user_id, FinancialGoal.status == "ativo")
        .order_by(FinancialGoal.created_at.desc())
        .limit(8)
        .all()
    )
    target = (
        db.query(MonthlyFinancialTarget)
        .filter(MonthlyFinancialTarget.user_id == user_id, MonthlyFinancialTarget.year == today.year, MonthlyFinancialTarget.month == today.month)
        .one_or_none()
    )
    reports = (
        db.query(FinancialMonthlyReport)
        .filter(FinancialMonthlyReport.user_id == user_id)
        .order_by(FinancialMonthlyReport.year.desc(), FinancialMonthlyReport.month.desc())
        .limit(12)
        .all()
    )
    history = list(reversed([
        {
            "year": r.year,
            "month": r.month,
            "classification": r.classification,
            "income": r.income,
            "expenses": r.expenses,
            "monthly_balance": r.monthly_balance,
            "emergency_reserve": r.emergency_reserve,
            "reserve_months": r.reserve_months,
        }
        for r in reports
    ]))

    next_steps = []
    if not profile.onboarding_completed:
        next_steps.append("Concluir onboarding para personalizar o FinanceOS por usuário.")
    if reserve_gap > 0:
        next_steps.append(f"Priorizar reserva de emergência: faltam R$ {reserve_gap:,.2f} para {profile.reserva_meses_alvo:.0f} meses.")
    if commitment is not None and commitment > 0.70:
        next_steps.append("Reduzir comprometimento mensal antes de assumir novas parcelas.")
    if profile.meta_investimento_mensal > 0 and balance >= profile.meta_investimento_mensal:
        next_steps.append("Manter aporte mensal planejado porque a sobra atual comporta a meta.")
    if not next_steps:
        next_steps.append("Manter controle mensal e revisar objetivos antes de novas dívidas.")

    return {
        "perfil": profile_to_dict(profile),
        "resumo": {
            "renda_mensal": income,
            "despesas_mensais": expenses,
            "saldo_mensal": balance,
            "comprometimento_pct": commitment,
            "fonte_core_disponivel": core.get("fonte"),
        },
        "saude_financeira": {
            "classificacao": classification,
            "diagnostico": diagnosis,
            "fatores": [
                f"Comprometimento de renda: {commitment * 100:.1f}%" if commitment is not None else "Comprometimento não calculado por renda zerada.",
                f"Reserva cobre {reserve_months:.1f} meses de despesas.",
                f"Saldo mensal estimado: R$ {balance:,.2f}.",
            ],
        },
        "objetivos": [goal_to_dict(g) for g in goals],
        "meta_mensal": target_to_dict(target) if target else None,
        "reserva_emergencia": {
            "atual": profile.reserva_emergencia,
            "meta": reserve_target,
            "gap": reserve_gap,
            "meses_cobertos": reserve_months,
            "meses_alvo": profile.reserva_meses_alvo,
        },
        "evolucao_historica": history,
        "relatorio_mensal": history[-1] if history else None,
        "proximos_passos": next_steps,
    }


def generate_monthly_report(db: Session, user_id: int, year: int, month: int) -> FinancialMonthlyReport:
    dashboard = build_executive_dashboard(db, user_id)
    resumo = dashboard["resumo"]
    saude = dashboard["saude_financeira"]
    reserva = dashboard["reserva_emergencia"]
    diagnosis = (
        f"{saude['diagnostico']} Saldo mensal de R$ {resumo['saldo_mensal']:,.2f}; "
        f"reserva cobre {reserva['meses_cobertos']:.1f} meses."
    )
    report = (
        db.query(FinancialMonthlyReport)
        .filter(FinancialMonthlyReport.user_id == user_id, FinancialMonthlyReport.year == year, FinancialMonthlyReport.month == month)
        .one_or_none()
    )
    payload = {
        "classification": saude["classificacao"],
        "diagnosis_text": diagnosis,
        "income": resumo["renda_mensal"],
        "expenses": resumo["despesas_mensais"],
        "monthly_balance": resumo["saldo_mensal"],
        "emergency_reserve": reserva["atual"],
        "reserve_months": reserva["meses_cobertos"],
        "payload_json": dashboard,
    }
    if report is None:
        report = FinancialMonthlyReport(user_id=user_id, year=year, month=month, **payload)
        db.add(report)
    else:
        for key, value in payload.items():
            setattr(report, key, value)
    db.commit()
    db.refresh(report)
    return report


def report_to_dict(report: FinancialMonthlyReport) -> dict[str, Any]:
    return {
        "id": report.id,
        "year": report.year,
        "month": report.month,
        "classification": report.classification,
        "diagnosis_text": report.diagnosis_text,
        "income": report.income,
        "expenses": report.expenses,
        "monthly_balance": report.monthly_balance,
        "emergency_reserve": report.emergency_reserve,
        "reserve_months": report.reserve_months,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }

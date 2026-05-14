from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.financial.models import FinancialDecisionHistory, FinancialGoal
from backend.app.financial.schemas import (
    AdvancedAdvisorRequest,
    AdvancedAdvisorResponse,
    ExecutiveDashboardResponse,
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
    FinancialCapacityResponse,
    FinancialDashboardResponse,
    FinancialDecisionHistoryResponse,
    FinancialSummaryResponse,
    GoalRequest,
    GoalResponse,
    InvestmentAdviceRequest,
    InvestmentAdviceResponse,
    MonthlyReportResponse,
    MonthlyTargetRequest,
    MonthlyTargetResponse,
    UserProfileResponse,
    UserProfileUpsertRequest,
)
from backend.app.financial.services.advanced_advisor import build_advanced_advisor
from backend.app.financial.services.decision_engine import build_central_decision
from backend.app.financial.services.financial_analysis import analyze_financing_decision, get_financial_capacity, get_financial_summary
from backend.app.financial.services.investment_advisor import build_investment_advice
from backend.app.financial.services.profile_dashboard import (
    build_executive_dashboard,
    create_goal,
    ensure_profile,
    generate_monthly_report,
    goal_to_dict,
    profile_to_dict,
    report_to_dict,
    target_to_dict,
    upsert_monthly_target,
    upsert_profile,
)
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.investment.portfolio_allocator import PortfolioAllocator
from backend.app.decision.decision_engine import decide_financial_path
from backend.app.market.services.market_data_service import MarketDataService

router = APIRouter(prefix="/financial", tags=["Financial Decision"])


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    return profile_to_dict(ensure_profile(db, auth.user_id))


@router.put("/profile", response_model=UserProfileResponse)
def save_profile(
    payload: UserProfileUpsertRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    return profile_to_dict(upsert_profile(db, auth.user_id, payload.model_dump()))


@router.post("/onboarding", response_model=UserProfileResponse)
def complete_onboarding(
    payload: UserProfileUpsertRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    data = payload.model_dump()
    data["onboarding_completed"] = True
    return profile_to_dict(upsert_profile(db, auth.user_id, data))


@router.get("/goals", response_model=list[GoalResponse])
def list_goals(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    rows = (
        db.query(FinancialGoal)
        .filter(FinancialGoal.user_id == auth.user_id)
        .order_by(FinancialGoal.created_at.desc())
        .all()
    )
    return [goal_to_dict(row) for row in rows]


@router.post("/goals", response_model=GoalResponse)
def add_goal(
    payload: GoalRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    data = payload.model_dump()
    if data.get("prazo"):
        data["prazo"] = date.fromisoformat(data["prazo"])
    return goal_to_dict(create_goal(db, auth.user_id, data))


@router.put("/monthly-target", response_model=MonthlyTargetResponse)
def save_monthly_target(
    payload: MonthlyTargetRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    return target_to_dict(upsert_monthly_target(db, auth.user_id, payload.model_dump()))


@router.get("/dashboard/executive", response_model=ExecutiveDashboardResponse)
def executive_dashboard(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    return build_executive_dashboard(db, auth.user_id)


@router.post("/reports/monthly", response_model=MonthlyReportResponse)
def monthly_report(
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    today = date.today()
    report = generate_monthly_report(db, auth.user_id, year or today.year, month or today.month)
    return {"report": report_to_dict(report)}


@router.post("/advisor/advanced", response_model=AdvancedAdvisorResponse)
def advanced_financial_advisor(
    payload: AdvancedAdvisorRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    """Consultor financeiro avançado: decide, prioriza, projeta e guia."""
    profile = ensure_profile(db, auth.user_id)
    profile_dict = profile_to_dict(profile)
    core = get_financial_summary() if payload.usar_dados_core else {}
    income = float(profile.renda_mensal or core.get("renda_total") or 0)
    expenses = float(profile.despesas_mensais or core.get("despesas_totais") or 0)
    investment_target = float(
        payload.investimento_mensal_planejado
        if payload.investimento_mensal_planejado is not None
        else profile.meta_investimento_mensal
    )

    financing_analysis = None
    if payload.financing is not None:
        financing_analysis = analyze_financing_decision(
            financing=payload.financing,
            renda_mensal=income or None,
            despesas_mensais=expenses or None,
            saldo_disponivel=max(income - expenses, 0),
            usar_dados_core=False,
        )

    monthly_debt = float((financing_analysis or {}).get("parcela_simulada") or 0)
    investment_advice = build_investment_advice(
        income=income,
        expenses=expenses,
        emergency_reserve=profile.reserva_emergencia,
        available_capital=0,
        monthly_investment_capacity=investment_target,
        risk_profile=profile.perfil_risco,
        monthly_debt_payment=monthly_debt,
    )

    history_rows = (
        db.query(FinancialDecisionHistory)
        .filter(FinancialDecisionHistory.user_id == auth.user_id)
        .order_by(FinancialDecisionHistory.created_at.desc())
        .limit(5)
        .all()
    )
    history = [{
        "classification": row.classification,
        "monthly_balance": row.monthly_balance,
        "reserve_months": (row.emergency_reserve / row.expenses) if row.expenses else 0,
    } for row in history_rows]

    advisor = build_advanced_advisor(
        profile=profile_dict,
        income=income,
        expenses=expenses,
        emergency_reserve=profile.reserva_emergencia,
        investment_target=investment_target,
        financing_analysis=financing_analysis,
        investment_advice=investment_advice,
        history=history,
    )
    portfolio_allocation = PortfolioAllocator().allocate(
        capital=investment_target,
        profile=profile.perfil_risco,
        monthly_income=income,
        monthly_expenses=expenses,
        emergency_reserve=profile.reserva_emergencia,
        monthly_debt_payment=monthly_debt,
    )
    advisor.setdefault("integracao_total", {})["alocacao_multiativos"] = portfolio_allocation
    advisor["integracao_total"]["mensagem_multiativos"] = "A carteira multiativos foi ajustada considerando reserva, dívida e capacidade real de investimento."

    db.add(FinancialDecisionHistory(
        user_id=auth.user_id,
        decision_type="advanced_advisor",
        classification=advisor["classificacao"],
        decision=advisor["decisao"],
        income=income,
        expenses=expenses,
        monthly_balance=income - expenses - monthly_debt,
        emergency_reserve=profile.reserva_emergencia,
        monthly_payment=monthly_debt or None,
        payload_json={"advisor": advisor, "financing_analysis": financing_analysis, "investment_advice": investment_advice},
        diagnosis_text=advisor["diagnostico"],
    ))
    db.commit()
    return advisor


@router.get("/summary", response_model=FinancialSummaryResponse)
def financial_summary(auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return get_financial_summary()


@router.get("/capacity", response_model=FinancialCapacityResponse)
def financial_capacity(auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    return get_financial_capacity()


@router.post("/analysis", response_model=FinancialAnalysisResponse)
def financial_analysis(
    payload: FinancialAnalysisRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    profile = ensure_profile(db, auth.user_id)
    analysis = analyze_financing_decision(
        financing=payload.financing,
        renda_mensal=payload.renda_mensal or profile.renda_mensal or None,
        despesas_mensais=payload.despesas_mensais or profile.despesas_mensais or None,
        saldo_disponivel=payload.saldo_disponivel,
        usar_dados_core=payload.usar_dados_core,
    )
    central = build_central_decision(analysis, None)
    db.add(FinancialDecisionHistory(
        user_id=auth.user_id,
        decision_type="financing",
        classification=analysis["classificacao"],
        decision=central["decisao"],
        income=analysis["renda_total"],
        expenses=analysis["despesas_totais"],
        monthly_balance=analysis["saldo_mensal"],
        emergency_reserve=profile.reserva_emergencia,
        monthly_payment=analysis["parcela_simulada"],
        payload_json={"analysis": analysis, "central_decision": central},
        diagnosis_text=central["diagnostico"],
    ))
    db.commit()
    return analysis


def _context_from_payload(payload: InvestmentAdviceRequest, profile_income: float, profile_expenses: float) -> tuple[float, float]:
    if payload.usar_dados_core:
        summary = get_financial_summary()
        return float(payload.renda_mensal or profile_income or summary["renda_total"]), float(payload.despesas_mensais or profile_expenses or summary["despesas_totais"])
    return float(payload.renda_mensal or profile_income or 0), float(payload.despesas_mensais or profile_expenses or 0)


@router.post("/investments/advice", response_model=InvestmentAdviceResponse)
def investment_advice(
    payload: InvestmentAdviceRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    profile = ensure_profile(db, auth.user_id)
    renda, despesas = _context_from_payload(payload, profile.renda_mensal, profile.despesas_mensais)
    reserva = payload.reserva_emergencia if payload.reserva_emergencia > 0 else profile.reserva_emergencia
    advice = build_investment_advice(
        income=renda,
        expenses=despesas,
        emergency_reserve=reserva,
        available_capital=payload.capital_disponivel,
        monthly_investment_capacity=payload.capacidade_investimento_mensal or profile.meta_investimento_mensal,
        risk_profile=payload.perfil_risco or profile.perfil_risco,
        monthly_debt_payment=payload.parcela_divida_mensal,
    )
    central = build_central_decision(None, advice)
    db.add(FinancialDecisionHistory(
        user_id=auth.user_id,
        decision_type="investment",
        classification=central["classificacao_geral"],
        decision=central["decisao"],
        income=advice["renda_mensal"],
        expenses=advice["despesas_mensais"],
        monthly_balance=advice["saldo_mensal"],
        emergency_reserve=advice["reserva_emergencia_atual"],
        monthly_payment=None,
        payload_json={"investment_advice": advice, "central_decision": central},
        diagnosis_text=central["diagnostico"],
    ))
    db.commit()
    return advice


@router.post("/decision/advanced")
def advanced_decision_core(
    payload: InvestmentAdviceRequest,
    db: Session = Depends(get_db),
    auth: AuthenticatedUser = Depends(require_authenticated_user),
):
    profile = ensure_profile(db, auth.user_id)
    renda, despesas = _context_from_payload(payload, profile.renda_mensal, profile.despesas_mensais)
    reserva = payload.reserva_emergencia if payload.reserva_emergencia > 0 else profile.reserva_emergencia
    market_context = MarketDataService(db).market_context_for_decision()
    allocation = PortfolioAllocator().allocate(
        capital=payload.capital_disponivel or payload.capacidade_investimento_mensal or profile.meta_investimento_mensal or 0,
        profile=payload.perfil_risco or profile.perfil_risco,
        monthly_income=renda,
        monthly_expenses=despesas,
        emergency_reserve=reserva,
        monthly_debt_payment=payload.parcela_divida_mensal,
        market_context=market_context,
    )
    decision = decide_financial_path(
        renda=renda,
        despesas=despesas,
        divida_mensal=payload.parcela_divida_mensal,
        reserva=reserva,
        perfil=payload.perfil_risco or profile.perfil_risco,
        allocation=allocation,
        market_context=market_context,
    )
    db.add(FinancialDecisionHistory(
        user_id=auth.user_id,
        decision_type="advanced_decision_core",
        classification=decision["classificacao"],
        decision=decision["decisao"],
        income=renda,
        expenses=despesas,
        monthly_balance=renda - despesas - payload.parcela_divida_mensal,
        emergency_reserve=reserva,
        monthly_payment=payload.parcela_divida_mensal or None,
        payload_json={"allocation": allocation, "decision": decision, "market_context": market_context},
        diagnosis_text=decision["diagnostico"],
    ))
    db.commit()
    return {"decision": decision, "allocation": allocation, "market_context": market_context}


@router.get("/dashboard", response_model=FinancialDashboardResponse)
def financial_dashboard(auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    resumo = get_financial_summary()
    capacidade = get_financial_capacity()
    investimento = build_investment_advice(
        income=resumo["renda_total"],
        expenses=resumo["despesas_totais"],
        emergency_reserve=0,
        risk_profile="conservador",
    )
    comprometimento = resumo.get("comprometimento_atual_pct") or 0
    saldo_ratio = (resumo["saldo_mensal"] / resumo["renda_total"]) if resumo["renda_total"] > 0 else 0
    if resumo["renda_total"] <= 0 or saldo_ratio <= 0:
        status = "arriscado"
        texto = "Cadastre renda e reduza despesas para transformar o FinanceOS em um consultor completo."
    elif comprometimento <= 0.60 and saldo_ratio >= 0.20:
        status = "seguro"
        texto = "Sua saúde financeira está boa: há margem mensal para planejar financiamento e investimentos."
    elif comprometimento <= 0.75 and saldo_ratio > 0:
        status = "moderado"
        texto = "Sua saúde financeira é intermediária: decisões novas devem preservar caixa e reserva."
    else:
        status = "arriscado"
        texto = "Sua saúde financeira exige atenção: o orçamento está muito comprometido."
    return {
        "resumo": resumo,
        "capacidade": capacidade,
        "saude_financeira": {
            "classificacao": status,
            "diagnostico": texto,
            "comprometimento_atual_pct": resumo.get("comprometimento_atual_pct"),
            "saldo_ratio": round(saldo_ratio, 6),
        },
        "investimento_base": investimento,
        "proximos_passos": [
            capacidade["recomendacao_textual"],
            investimento["mensagem"],
            "Use simulações comparadas antes de assumir qualquer parcela nova.",
        ],
    }


@router.get("/decisions/history", response_model=FinancialDecisionHistoryResponse)
def decision_history(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    rows = (
        db.query(FinancialDecisionHistory)
        .filter(FinancialDecisionHistory.user_id == auth.user_id)
        .order_by(FinancialDecisionHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return {"history": [{
        "id": row.id,
        "decision_type": row.decision_type,
        "classification": row.classification,
        "decision": row.decision,
        "income": row.income,
        "expenses": row.expenses,
        "monthly_balance": row.monthly_balance,
        "emergency_reserve": row.emergency_reserve,
        "monthly_payment": row.monthly_payment,
        "diagnosis_text": row.diagnosis_text,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]}

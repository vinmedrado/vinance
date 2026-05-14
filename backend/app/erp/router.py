from __future__ import annotations

from datetime import date
from typing import Type

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.erp.models import ERPAccount, ERPBudget, ERPCard, ERPCategory, ERPExpense, ERPIncome, ERPPlannedInvestment
from backend.app.erp.schemas import (
    AccountIn, AccountOut, BudgetIn, BudgetOut, CardIn, CardOut, CategoryIn, CategoryOut,
    DashboardOut, DiagnosisOut, ExpenseIn, ExpenseOut, GoalIn, GoalOut, IncomeIn, IncomeOut,
    PlannedInvestmentIn, PlannedInvestmentOut,
)
from backend.app.erp.service import apply_budget_model, build_dashboard, build_diagnosis
from backend.app.enterprise.audit import record_audit_log
from backend.app.financial.models import FinancialGoal
from backend.app.enterprise.context import TenantContext, get_tenant_context, require_permission
from backend.app.services.plan_limits_service import PlanLimitExceeded, ensure_feature_allowed

router = APIRouter(prefix="/api", tags=["ERP Financeiro Premium"])


def _tenant(ctx: TenantContext) -> str:
    return ctx.organization_id


def _legacy_user_id(ctx: TenantContext) -> int | None:
    try:
        return int(ctx.user_id)
    except (TypeError, ValueError):
        return None


def _get_owned(db: Session, model: Type, row_id: int, tenant_id: str):
    row = db.query(model).filter(model.id == row_id, model.organization_id == tenant_id, model.deleted_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return row


def _enforce_limit(db: Session, ctx: TenantContext, feature: str) -> None:
    try:
        ensure_feature_allowed(db, organization_id=_tenant(ctx), plan=ctx.plan, feature=feature)
    except PlanLimitExceeded as exc:
        raise HTTPException(status_code=403, detail={"detail": "Plan limit reached", "limit": feature, "plan": ctx.plan, "upgrade_required": True, "message": str(exc)})

def _audit(db: Session, request: Request | None, ctx: TenantContext, action: str, entity_type: str, entity_id: str | None = None, before=None, after=None) -> None:
    record_audit_log(db, organization_id=_tenant(ctx), user_id=ctx.user_id, action=action, entity_type=entity_type, entity_id=entity_id, before=before, after=after, ip_address=request.client.host if request and request.client else None, user_agent=request.headers.get("user-agent") if request else None, request_id=getattr(request.state, "request_id", None) if request else None)


@router.get("/me")
def me(ctx: TenantContext = Depends(get_tenant_context)):
    raw = ctx.raw if isinstance(ctx.raw, dict) else {}
    return {"id": ctx.user_id, "email": raw.get("email"), "role": ctx.role, "plan": ctx.plan}


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.view"))):
    return build_dashboard(db, _tenant(ctx), year, month)


@router.get("/financial-diagnosis", response_model=DiagnosisOut)
def diagnosis(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    return build_diagnosis(db, _tenant(ctx), year, month)


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(year: int | None = None, month: int | None = None, status: str | None = None, category: str | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.view"))):
    q = db.query(ERPExpense).filter(ERPExpense.organization_id == _tenant(ctx), ERPExpense.deleted_at.is_(None))
    if year:
        from sqlalchemy import extract
        q = q.filter(extract("year", ERPExpense.due_date) == year)
    if month:
        from sqlalchemy import extract
        q = q.filter(extract("month", ERPExpense.due_date) == month)
    if status:
        q = q.filter(ERPExpense.status == status)
    if category:
        q = q.filter(ERPExpense.category == category)
    return q.order_by(ERPExpense.due_date.desc()).all()


@router.post("/expenses", response_model=ExpenseOut)
def create_expense(payload: ExpenseIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.create"))):
    _enforce_limit(db, ctx, "expenses_per_month")
    row = ERPExpense(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush()
    _audit(db, request, ctx, "expense.created", "expense", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row)
    return row


@router.put("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, payload: ExpenseIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.edit"))):
    row = _get_owned(db, ERPExpense, expense_id, _tenant(ctx))
    before = {"id": row.id, "amount": getattr(row, "amount", None), "description": getattr(row, "description", None)}
    for k, v in payload.model_dump().items(): setattr(row, k, v)
    row.updated_by = ctx.user_id
    _audit(db, request, ctx, "expense.updated" if isinstance(row, ERPExpense) else "income.updated", "expense" if isinstance(row, ERPExpense) else "income", str(row.id), before=before, after=payload.model_dump())
    db.commit(); db.refresh(row)
    return row


@router.patch("/expenses/{expense_id}/status", response_model=ExpenseOut)
def update_expense_status(expense_id: int, request: Request, status: str = Query(...), db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.edit"))):
    row = _get_owned(db, ERPExpense, expense_id, _tenant(ctx))
    before = {"status": row.status, "paid_at": row.paid_at}
    row.status = status
    if status == "paid" and not row.paid_at:
        row.paid_at = date.today()
    row.updated_by = ctx.user_id
    _audit(db, request, ctx, "expense.marked_paid" if status == "paid" else "expense.updated", "expense", str(row.id), before=before, after={"status": status, "paid_at": row.paid_at})
    db.commit(); db.refresh(row)
    return row


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.delete"))):
    row = _get_owned(db, ERPExpense, expense_id, _tenant(ctx))
    row.deleted_at = date.today()
    row.updated_by = ctx.user_id
    _audit(db, request, ctx, "expense.deleted", "expense", str(expense_id), before={"id": expense_id})
    db.commit()
    return {"ok": True}


@router.get("/incomes", response_model=list[IncomeOut])
def list_incomes(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("incomes.view"))):
    return db.query(ERPIncome).filter_by(organization_id=_tenant(ctx), deleted_at=None).order_by(ERPIncome.received_at.desc()).all()


@router.post("/incomes", response_model=IncomeOut)
def create_income(payload: IncomeIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("incomes.create"))):
    row = ERPIncome(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush()
    _audit(db, request, ctx, "income.created", "income", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row)
    return row


@router.put("/incomes/{income_id}", response_model=IncomeOut)
def update_income(income_id: int, payload: IncomeIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("incomes.edit"))):
    row = _get_owned(db, ERPIncome, income_id, _tenant(ctx))
    before = {"id": row.id, "amount": getattr(row, "amount", None), "description": getattr(row, "description", None)}
    for k, v in payload.model_dump().items(): setattr(row, k, v)
    row.updated_by = ctx.user_id
    _audit(db, request, ctx, "income.updated", "income", str(row.id), before=before, after=payload.model_dump())
    db.commit(); db.refresh(row)
    return row


@router.delete("/incomes/{income_id}")
def delete_income(income_id: int, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("incomes.delete"))):
    row = _get_owned(db, ERPIncome, income_id, _tenant(ctx))
    row.deleted_at = date.today(); row.updated_by = ctx.user_id
    _audit(db, request, ctx, "income.deleted", "income", str(income_id), before={"id": income_id})
    db.commit(); return {"ok": True}


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("accounts.view"))):
    return db.query(ERPAccount).filter_by(organization_id=_tenant(ctx), is_active=True, deleted_at=None).order_by(ERPAccount.name).all()


@router.post("/accounts", response_model=AccountOut)
def create_account(payload: AccountIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("accounts.manage"))):
    _enforce_limit(db, ctx, "accounts")
    row = ERPAccount(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, request, ctx, "account.created", "account", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row); return row


@router.get("/cards", response_model=list[CardOut])
def list_cards(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("cards.view"))):
    return db.query(ERPCard).filter_by(organization_id=_tenant(ctx), is_active=True, deleted_at=None).order_by(ERPCard.name).all()


@router.post("/cards", response_model=CardOut)
def create_card(payload: CardIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("cards.manage"))):
    row = ERPCard(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, request, ctx, "card.created", "card", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row); return row


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(kind: str | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("expenses.view"))):
    q = db.query(ERPCategory).filter(ERPCategory.organization_id == _tenant(ctx), ERPCategory.deleted_at.is_(None))
    if kind: q = q.filter(ERPCategory.kind == kind)
    return q.order_by(ERPCategory.name).all()


@router.post("/categories", response_model=CategoryOut)
def create_category(payload: CategoryIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("budgets.manage"))):
    row = ERPCategory(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, request, ctx, "category.created", "category", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row); return row


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("budgets.view"))):
    return db.query(ERPBudget).filter_by(organization_id=_tenant(ctx), deleted_at=None).order_by(ERPBudget.year.desc(), ERPBudget.month.desc()).all()


@router.post("/budgets", response_model=BudgetOut)
def upsert_budget(payload: BudgetIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("budgets.manage"))):
    data = apply_budget_model(payload.model, payload.model_dump(exclude_none=True))
    row = db.query(ERPBudget).filter_by(organization_id=_tenant(ctx), year=payload.year, month=payload.month, deleted_at=None).first()
    if not row:
        row = ERPBudget(organization_id=_tenant(ctx), created_by=ctx.user_id, **data)
        db.add(row); db.flush(); _audit(db, request, ctx, "budget.created", "budget", str(row.id), after=data)
    else:
        before = {"id": row.id, "model": row.model}
        for k, v in data.items(): setattr(row, k, v)
        row.updated_by = ctx.user_id
        _audit(db, request, ctx, "budget.model_changed" if before.get("model") != data.get("model") else "budget.updated", "budget", str(row.id), before=before, after=data)
    db.commit(); db.refresh(row); return row


@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("goals.view"))):
    return db.query(FinancialGoal).filter_by(organization_id=_tenant(ctx), deleted_at=None).order_by(FinancialGoal.created_at.desc()).all()


@router.post("/goals", response_model=GoalOut)
def create_goal(payload: GoalIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("goals.create"))):
    _enforce_limit(db, ctx, "goals")
    row = FinancialGoal(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, request, ctx, "goal.created", "goal", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row); return row


@router.get("/investments", response_model=list[PlannedInvestmentOut])
def list_planned_investments(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    return db.query(ERPPlannedInvestment).filter_by(organization_id=_tenant(ctx), deleted_at=None).order_by(ERPPlannedInvestment.year.desc(), ERPPlannedInvestment.month.desc()).all()


@router.post("/investments", response_model=PlannedInvestmentOut)
def create_planned_investment(payload: PlannedInvestmentIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.manage"))):
    row = ERPPlannedInvestment(organization_id=_tenant(ctx), created_by=ctx.user_id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, request, ctx, "investment.created", "planned_investment", str(row.id), after=payload.model_dump())
    db.commit(); db.refresh(row); return row


@router.get("/portfolio")
def portfolio():
    return {"positions": [], "message": "Carteira conectada ao módulo de investimentos existente; cadastre ativos para visualizar alocação."}


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("alerts.view"))):
    diagnosis = build_diagnosis(db, _tenant(ctx))
    return {"alerts": diagnosis["alerts"]}


@router.get("/plans")
def plans():
    return {
        "plans": [
            {"name": "Free", "price": "R$ 0", "features": ["Controle básico", "Dashboard financeiro", "Orçamento mensal"]},
            {"name": "Pro", "price": "R$ 39/mês", "features": ["Diagnóstico inteligente", "Alertas", "Carteira", "Oportunidades"]},
            {"name": "Premium", "price": "Sob consulta", "features": ["Automações", "API", "Relatórios", "Multiusuário"]},
        ],
        "stripe_status": "configure STRIPE_SECRET_KEY para ativar checkout real",
    }


@router.get("/health")
def api_health():
    return {"status": "ok", "service": "financeos-api", "frontend": "react", "backend": "fastapi"}

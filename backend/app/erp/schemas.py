from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class BaseOut(BaseModel):
    id: int
    class Config:
        from_attributes = True

class AccountIn(BaseModel):
    name: str
    type: str = "checking"
    institution: str | None = None
    balance: float = 0

class AccountOut(AccountIn, BaseOut):
    is_active: bool = True

class CardIn(BaseModel):
    name: str
    brand: str | None = None
    limit_amount: float = 0
    closing_day: int | None = None
    due_day: int | None = None

class CardOut(CardIn, BaseOut):
    is_active: bool = True

class CategoryIn(BaseModel):
    name: str
    kind: str = "expense"
    group: str | None = None
    color: str | None = None

class CategoryOut(CategoryIn, BaseOut):
    pass

class ExpenseIn(BaseModel):
    amount: float = Field(gt=0)
    description: str
    category_id: int | None = None
    category: str | None = None
    subcategory: str | None = None
    due_date: date
    paid_at: date | None = None
    recurrence: str = "none"
    payment_method: str | None = None
    account_id: int | None = None
    card_id: int | None = None
    status: str = "pending"
    tags: str | None = None
    notes: str | None = None
    attachment_url: str | None = None

class ExpenseOut(ExpenseIn, BaseOut):
    created_at: datetime | None = None

class IncomeIn(BaseModel):
    amount: float = Field(gt=0)
    description: str
    category_id: int | None = None
    account_id: int | None = None
    received_at: date
    recurrence: str = "none"
    status: str = "received"
    notes: str | None = None

class IncomeOut(IncomeIn, BaseOut):
    created_at: datetime | None = None

class BudgetIn(BaseModel):
    year: int
    month: int
    model: str = "50_30_20"
    monthly_income: float = 0
    needs_pct: float | None = None
    wants_pct: float | None = None
    investments_pct: float | None = None
    custom_json: str | None = None

class BudgetOut(BaseOut):
    year: int
    month: int
    model: str
    monthly_income: float
    needs_pct: float
    wants_pct: float
    investments_pct: float
    custom_json: str | None = None

class GoalIn(BaseModel):
    nome: str
    tipo: str = "geral"
    valor_alvo: float = 0
    valor_atual: float = 0
    prazo: date | None = None
    prioridade: str = "media"
    status: str = "ativo"

class GoalOut(GoalIn, BaseOut):
    pass

class PlannedInvestmentIn(BaseModel):
    year: int
    month: int
    planned_amount: float = 0
    realized_amount: float = 0
    target_asset_class: str | None = None
    notes: str | None = None

class PlannedInvestmentOut(PlannedInvestmentIn, BaseOut):
    pass

class DashboardOut(BaseModel):
    period: dict[str, int]
    metrics: dict[str, float]
    budget: dict[str, Any]
    charts: dict[str, Any]
    recommendation: dict[str, str | float]
    alerts: list[dict[str, Any]]

class DiagnosisOut(BaseModel):
    score: int
    status: str
    alerts: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    forecast: dict[str, Any]
    investment_connection: dict[str, Any]

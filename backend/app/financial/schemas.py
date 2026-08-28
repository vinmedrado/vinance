from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskProfile = Literal["conservative", "moderate", "aggressive"]


class IncomeCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    income_type: str = Field(min_length=1, max_length=80)
    received_at: date
    is_recurring: bool = False


class IncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    description: str
    amount: Decimal
    income_type: str
    received_at: date
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    category: str = Field(min_length=1, max_length=100)
    due_date: date
    paid_at: date | None = None
    is_paid: bool = False
    is_recurring: bool = False


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    description: str
    amount: Decimal
    category: str
    due_date: date
    paid_at: date | None
    is_paid: bool
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


class FinancialProfileCreate(BaseModel):
    monthly_salary: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    emergency_reserve: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    has_debt_default: bool = False
    risk_profile: RiskProfile


class FinancialProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    monthly_salary: Decimal
    emergency_reserve: Decimal
    has_debt_default: bool
    risk_profile: RiskProfile
    created_at: datetime
    updated_at: datetime


class FinancialScoreRead(BaseModel):
    score: int
    level: Literal["critical", "attention", "healthy", "excellent"]
    penalties: list[str]
    recommendations: list[str]


class BudgetDiagnosisRead(BaseModel):
    method: str
    committed_ratio: Decimal
    total_expenses_30d: Decimal
    investment_percentage: Decimal
    investment_capacity: Decimal
    emergency_reserve_priority: bool
    high_risk_allowed: bool
    explanation: str


class FinancialDiagnosisRead(BaseModel):
    monthly_salary: Decimal
    total_expenses_30d: Decimal
    emergency_reserve: Decimal
    has_debt_default: bool
    risk_profile: RiskProfile
    score: FinancialScoreRead
    budget: BudgetDiagnosisRead

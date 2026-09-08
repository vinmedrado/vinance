from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


OwnershipScope = Literal["PERSONAL", "HOUSEHOLD"]
HouseholdStatus = Literal["ACTIVE", "ARCHIVED"]
MemberRole = Literal["OWNER", "MEMBER"]
MemberStatus = Literal["ACTIVE", "REMOVED"]
LiabilityStatus = Literal["ACTIVE", "PAID", "DEFAULTED", "CANCELLED"]
AssetClass = Literal[
    "CASH",
    "EMERGENCY_RESERVE",
    "FIXED_INCOME",
    "INVESTMENTS",
    "REAL_ESTATE",
    "VEHICLES",
    "OTHER",
]
AssetStatus = Literal["ACTIVE", "DISPOSED"]
GoalPriority = Literal["LOW", "MEDIUM", "HIGH"]
GoalStatus = Literal["ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"]
DataQuality = Literal["COMPLETE", "PARTIAL", "INSUFFICIENT", "STALE", "INCONSISTENT"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HouseholdCreate(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    household_type: Literal["SHARED"] = "SHARED"


class HouseholdUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: HouseholdStatus | None = None


class HouseholdRead(OrmModel):
    id: int
    name: str
    household_type: Literal["PERSONAL", "SHARED"]
    created_by_user_id: int
    status: HouseholdStatus
    created_at: datetime
    updated_at: datetime


class HouseholdMemberCreate(StrictModel):
    email: EmailStr
    role: MemberRole = "MEMBER"
    is_default: bool = False


class HouseholdMemberUpdate(StrictModel):
    role: MemberRole | None = None
    status: MemberStatus | None = None
    is_default: bool | None = None


class HouseholdMemberRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    role: MemberRole
    status: MemberStatus
    is_default: bool
    joined_at: datetime
    updated_at: datetime
    email: str | None = None
    full_name: str | None = None


class IncomeCreate(StrictModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    income_type: str = Field(min_length=1, max_length=80)
    received_at: date
    is_recurring: bool
    ownership_scope: OwnershipScope


class IncomeUpdate(StrictModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    income_type: str | None = Field(default=None, min_length=1, max_length=80)
    received_at: date | None = None
    is_recurring: bool | None = None
    ownership_scope: OwnershipScope | None = None


class IncomeRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    ownership_scope: OwnershipScope
    description: str
    amount: Decimal
    income_type: str
    received_at: date
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


class ExpenseCreate(StrictModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    category: str = Field(min_length=1, max_length=100)
    due_date: date
    paid_at: date | None = None
    is_paid: bool = False
    is_recurring: bool
    expense_nature: Literal["FIXED", "VARIABLE"]
    ownership_scope: OwnershipScope


class ExpenseUpdate(StrictModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    due_date: date | None = None
    paid_at: date | None = None
    is_paid: bool | None = None
    is_recurring: bool | None = None
    expense_nature: Literal["FIXED", "VARIABLE"] | None = None
    ownership_scope: OwnershipScope | None = None


class ExpenseRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    ownership_scope: OwnershipScope
    description: str
    amount: Decimal
    category: str
    due_date: date
    paid_at: date | None
    is_paid: bool
    is_recurring: bool
    expense_nature: Literal["FIXED", "VARIABLE"] | None
    created_at: datetime
    updated_at: datetime


class LiabilityCreate(StrictModel):
    ownership_scope: OwnershipScope
    name: str = Field(min_length=1, max_length=255)
    liability_type: str = Field(min_length=1, max_length=80)
    current_balance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    monthly_payment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    annual_interest_rate_pct: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=6)
    due_date: date | None = None
    balance_as_of: date | None = None
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    status: LiabilityStatus = "ACTIVE"


class LiabilityUpdate(StrictModel):
    ownership_scope: OwnershipScope | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    liability_type: str | None = Field(default=None, min_length=1, max_length=80)
    current_balance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    monthly_payment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    annual_interest_rate_pct: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=6)
    due_date: date | None = None
    balance_as_of: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    status: LiabilityStatus | None = None


class LiabilityRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    ownership_scope: OwnershipScope
    name: str
    liability_type: str
    current_balance: Decimal | None
    monthly_payment: Decimal | None
    annual_interest_rate_pct: Decimal | None
    due_date: date | None
    balance_as_of: date | None
    currency: str
    status: LiabilityStatus
    created_at: datetime
    updated_at: datetime


class AssetCreate(StrictModel):
    ownership_scope: OwnershipScope
    asset_class: AssetClass
    asset_catalog_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    current_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    value_as_of: date | None = None
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    status: AssetStatus = "ACTIVE"

    @model_validator(mode="after")
    def validate_identity(self) -> "AssetCreate":
        if self.name is None and self.asset_catalog_id is None:
            raise ValueError("name or asset_catalog_id is required")
        return self


class AssetUpdate(StrictModel):
    ownership_scope: OwnershipScope | None = None
    asset_class: AssetClass | None = None
    asset_catalog_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    current_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    value_as_of: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    status: AssetStatus | None = None


class AssetRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    ownership_scope: OwnershipScope
    asset_class: AssetClass
    asset_catalog_id: int | None
    name: str | None
    current_value: Decimal | None
    value_as_of: date | None
    currency: str
    status: AssetStatus
    created_at: datetime
    updated_at: datetime


class GoalCreate(StrictModel):
    ownership_scope: OwnershipScope
    name: str = Field(min_length=1, max_length=255)
    target_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    current_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    deadline: date | None = None
    priority: GoalPriority
    status: GoalStatus = "ACTIVE"
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")


class GoalUpdate(StrictModel):
    ownership_scope: OwnershipScope | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    current_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    deadline: date | None = None
    priority: GoalPriority | None = None
    status: GoalStatus | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class GoalRead(OrmModel):
    id: int
    household_id: int
    user_id: int
    ownership_scope: OwnershipScope
    name: str
    target_amount: Decimal
    current_amount: Decimal | None
    deadline: date | None
    priority: GoalPriority
    status: GoalStatus
    currency: str
    created_at: datetime
    updated_at: datetime


class FinancialStateRead(BaseModel):
    household_id: int
    engine_version: str
    evaluated_at: datetime
    metrics: dict[str, Any]
    goals: list[dict[str, Any]]
    member_views: list[dict[str, Any]]
    data_quality: DataQuality
    confidence: int = Field(ge=0, le=100)
    missing_fields: list[str]
    inconsistencies: list[str]
    stale_fields: list[str]
    provenance: dict[str, Any]


class FinancialStateSnapshotRead(OrmModel):
    id: int
    household_id: int
    created_by_user_id: int
    evaluated_at: datetime
    engine_version: str
    normalized_inputs: dict[str, Any]
    metrics: dict[str, Any]
    member_views: list[dict[str, Any]]
    data_quality: DataQuality
    confidence: int = Field(ge=0, le=100)
    missing_fields: list[str]
    inconsistencies: list[str]
    input_fingerprint: str
    idempotency_key: str | None
    created_at: datetime


class FinancialStateHistory(BaseModel):
    items: list[FinancialStateSnapshotRead]
    total: int = Field(ge=0)

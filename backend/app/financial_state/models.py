from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Household(Base):
    __tablename__ = "households"
    __table_args__ = (
        CheckConstraint("household_type IN ('PERSONAL','SHARED')", name="ck_households_type"),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_households_status"),
        Index("ix_households_creator_status", "created_by_user_id", "status"),
        Index(
            "uq_households_personal_creator",
            "created_by_user_id",
            unique=True,
            postgresql_where=text("household_type = 'PERSONAL' AND status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    household_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_members_household_user"),
        CheckConstraint("role IN ('OWNER','MEMBER')", name="ck_household_members_role"),
        CheckConstraint("status IN ('ACTIVE','REMOVED')", name="ck_household_members_status"),
        Index("ix_household_members_user_status", "user_id", "status"),
        Index(
            "uq_household_members_active_default_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default AND status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="MEMBER")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FinancialLiability(Base):
    __tablename__ = "financial_liabilities"
    __table_args__ = (
        CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_financial_liabilities_scope"),
        CheckConstraint("current_balance IS NULL OR current_balance >= 0", name="ck_financial_liabilities_balance"),
        CheckConstraint("monthly_payment IS NULL OR monthly_payment >= 0", name="ck_financial_liabilities_payment"),
        CheckConstraint(
            "annual_interest_rate_pct IS NULL OR annual_interest_rate_pct >= 0",
            name="ck_financial_liabilities_interest",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','PAID','DEFAULTED','CANCELLED')",
            name="ck_financial_liabilities_status",
        ),
        Index("ix_financial_liabilities_household_status", "household_id", "status"),
        Index("ix_financial_liabilities_owner", "household_id", "ownership_scope", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    ownership_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    liability_type: Mapped[str] = mapped_column(String(80), nullable=False)
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    annual_interest_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    balance_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OwnedAsset(Base):
    __tablename__ = "owned_assets"
    __table_args__ = (
        CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_owned_assets_scope"),
        CheckConstraint(
            "asset_class IN ('CASH','EMERGENCY_RESERVE','FIXED_INCOME','INVESTMENTS','REAL_ESTATE','VEHICLES','OTHER')",
            name="ck_owned_assets_class",
        ),
        CheckConstraint("current_value IS NULL OR current_value >= 0", name="ck_owned_assets_value"),
        CheckConstraint("name IS NOT NULL OR asset_catalog_id IS NOT NULL", name="ck_owned_assets_identity"),
        CheckConstraint("status IN ('ACTIVE','DISPOSED')", name="ck_owned_assets_status"),
        Index("ix_owned_assets_household_status", "household_id", "status"),
        Index("ix_owned_assets_owner", "household_id", "ownership_scope", "user_id"),
        Index("ix_owned_assets_catalog", "asset_catalog_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    ownership_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_catalog_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_catalog.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    value_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    __table_args__ = (
        CheckConstraint("ownership_scope IN ('PERSONAL','HOUSEHOLD')", name="ck_financial_goals_scope"),
        CheckConstraint("target_amount > 0", name="ck_financial_goals_target"),
        CheckConstraint("current_amount IS NULL OR current_amount >= 0", name="ck_financial_goals_current"),
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH')", name="ck_financial_goals_priority"),
        CheckConstraint(
            "status IN ('ACTIVE','PAUSED','COMPLETED','CANCELLED')",
            name="ck_financial_goals_status",
        ),
        Index("ix_financial_goals_household_status", "household_id", "status"),
        Index("ix_financial_goals_owner", "household_id", "ownership_scope", "user_id"),
        Index("ix_financial_goals_deadline", "household_id", "deadline"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    ownership_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    current_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FinancialStateSnapshot(Base):
    __tablename__ = "financial_state_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "household_id",
            name="uq_financial_state_snapshots_id_household",
        ),
        CheckConstraint(
            "data_quality IN ('COMPLETE','PARTIAL','INSUFFICIENT','STALE','INCONSISTENT')",
            name="ck_financial_state_snapshots_quality",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="ck_financial_state_snapshots_confidence"),
        Index("ix_financial_state_snapshots_household_evaluated", "household_id", "evaluated_at"),
        Index(
            "uq_financial_state_snapshots_idempotency",
            "household_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    member_views: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    data_quality: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    inconsistencies: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.database import Base


class ERPAccount(Base):
    __tablename__ = "erp_accounts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    name = Column(String(140), nullable=False)
    type = Column(String(40), nullable=False, default="checking")
    institution = Column(String(140), nullable=True)
    balance = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_erp_accounts_user_active", "user_id", "is_active"),)


class ERPCard(Base):
    __tablename__ = "erp_cards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    name = Column(String(140), nullable=False)
    brand = Column(String(60), nullable=True)
    limit_amount = Column(Float, nullable=False, default=0.0)
    closing_day = Column(Integer, nullable=True)
    due_day = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ERPCategory(Base):
    __tablename__ = "erp_categories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    name = Column(String(120), nullable=False)
    kind = Column(String(20), nullable=False, default="expense")
    group = Column(String(40), nullable=True)  # necessidades, desejos, investimentos, reserva
    color = Column(String(30), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", "kind", name="uq_erp_categories_org_name_kind"),)


class ERPIncome(Base):
    __tablename__ = "erp_incomes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    amount = Column(Float, nullable=False)
    description = Column(String(220), nullable=False)
    category_id = Column(Integer, nullable=True)
    account_id = Column(Integer, nullable=True)
    received_at = Column(Date, nullable=False)
    recurrence = Column(String(40), nullable=False, default="none")
    status = Column(String(20), nullable=False, default="received")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_erp_incomes_user_date", "user_id", "received_at"),)


class ERPExpense(Base):
    __tablename__ = "erp_expenses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    amount = Column(Float, nullable=False)
    description = Column(String(220), nullable=False)
    category_id = Column(Integer, nullable=True)
    category = Column(String(120), nullable=True)
    subcategory = Column(String(120), nullable=True)
    due_date = Column(Date, nullable=False)
    paid_at = Column(Date, nullable=True)
    recurrence = Column(String(40), nullable=False, default="none")
    payment_method = Column(String(60), nullable=True)
    account_id = Column(Integer, nullable=True)
    card_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    tags = Column(String(250), nullable=True)
    notes = Column(Text, nullable=True)
    attachment_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_erp_expenses_user_date_status", "user_id", "due_date", "status"), Index("ix_erp_expenses_org_date_status", "organization_id", "due_date", "status"),)


class ERPBudget(Base):
    __tablename__ = "erp_budgets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    model = Column(String(40), nullable=False, default="50_30_20")
    monthly_income = Column(Float, nullable=False, default=0.0)
    needs_pct = Column(Float, nullable=False, default=50.0)
    wants_pct = Column(Float, nullable=False, default=30.0)
    investments_pct = Column(Float, nullable=False, default=20.0)
    custom_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "year", "month", name="uq_erp_budget_org_month"),)


class ERPPlannedInvestment(Base):
    __tablename__ = "erp_planned_investments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    planned_amount = Column(Float, nullable=False, default=0.0)
    realized_amount = Column(Float, nullable=False, default=0.0)
    target_asset_class = Column(String(60), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ERPAlert(Base):
    __tablename__ = "erp_alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="info")
    source = Column(String(40), nullable=False, default="financial_diagnosis")
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

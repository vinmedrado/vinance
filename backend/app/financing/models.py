from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from backend.app.database import Base


class FinancingPreset(Base):
    __tablename__ = "financing_presets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    asset_type = Column(String(32), index=True, nullable=False)
    name = Column(String(120), nullable=False)
    bank_name = Column(String(120), nullable=True)
    default_monthly_rate = Column(Float, nullable=False)
    max_income_commitment_pct = Column(Float, nullable=False, default=0.30)
    admin_fee = Column(Float, nullable=False, default=0.0)
    operational_fee = Column(Float, nullable=False, default=0.0)
    appraisal_fee = Column(Float, nullable=False, default=0.0)
    registry_fee = Column(Float, nullable=False, default=0.0)
    insurance_monthly = Column(Float, nullable=False, default=0.0)
    mip_monthly = Column(Float, nullable=False, default=0.0)
    dfi_monthly = Column(Float, nullable=False, default=0.0)
    is_default = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "asset_type", "name", name="uq_financing_presets_user_asset_name"),
        Index("ix_financing_presets_user_asset", "user_id", "asset_type"),
    )


class FinancingSimulation(Base):
    __tablename__ = "financing_simulations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    asset_type = Column(String(32), index=True, nullable=False)
    system = Column(String(16), nullable=False)
    asset_value = Column(Float, nullable=False)
    down_payment = Column(Float, nullable=False)
    financed_amount = Column(Float, nullable=False)
    principal_with_costs = Column(Float, nullable=False)
    months = Column(Integer, nullable=False)
    monthly_rate = Column(Float, nullable=False)
    annual_effective_rate = Column(Float, nullable=False)
    estimated_cet_monthly = Column(Float, nullable=False)
    estimated_cet_annual = Column(Float, nullable=False)
    iof_scenario = Column(String(40), nullable=False, default="pf_auto")
    iof_amount = Column(Float, nullable=False, default=0.0)
    credit_one_time_costs = Column(Float, nullable=False, default=0.0)
    cet_components_json = Column(JSON, nullable=True)
    admin_fee = Column(Float, nullable=False, default=0.0)
    operational_fee = Column(Float, nullable=False, default=0.0)
    appraisal_fee = Column(Float, nullable=False, default=0.0)
    registry_fee = Column(Float, nullable=False, default=0.0)
    insurance_total = Column(Float, nullable=False, default=0.0)
    total_installments = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False)
    total_financed_cost = Column(Float, nullable=False)
    total_interest = Column(Float, nullable=False)
    first_payment = Column(Float, nullable=False)
    last_payment = Column(Float, nullable=False)
    average_payment = Column(Float, nullable=False)
    monthly_income = Column(Float, nullable=True)
    income_commitment_pct = Column(Float, nullable=True)
    ltv_pct = Column(Float, nullable=False)
    risk_level = Column(String(16), nullable=False)
    risk_score = Column(Integer, nullable=False)
    approved = Column(Boolean, nullable=True)
    approval_reason = Column(Text, nullable=True)
    input_json = Column(JSON, nullable=False)
    schedule_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        Index("ix_financing_simulations_user_created", "user_id", "created_at"),
        Index("ix_financing_simulations_user_asset", "user_id", "asset_type"),
    )


class FinancingHistory(Base):
    __tablename__ = "financing_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    simulation_id = Column(Integer, index=True, nullable=True)
    event_type = Column(String(40), nullable=False)
    payload_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (Index("ix_financing_history_user_created", "user_id", "created_at"),)

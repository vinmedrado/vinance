from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.database import Base


class FinancialUserProfile(Base):
    """Perfil financeiro persistido por usuário.

    Complementa o core legado sem substituir despesas, investimentos ou financiamento.
    """

    __tablename__ = "financial_user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    nome = Column(String(120), nullable=True)
    perfil_risco = Column(String(30), nullable=False, default="conservador")
    renda_mensal = Column(Float, nullable=False, default=0.0)
    despesas_mensais = Column(Float, nullable=False, default=0.0)
    reserva_emergencia = Column(Float, nullable=False, default=0.0)
    reserva_meses_alvo = Column(Float, nullable=False, default=6.0)
    meta_investimento_mensal = Column(Float, nullable=False, default=0.0)
    meta_economia_mensal = Column(Float, nullable=False, default=0.0)
    objetivo_principal = Column(String(200), nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    organization_id = Column(String(36), index=True, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    nome = Column(String(160), nullable=False)
    tipo = Column(String(40), nullable=False, default="geral")
    valor_alvo = Column(Float, nullable=False, default=0.0)
    valor_atual = Column(Float, nullable=False, default=0.0)
    prazo = Column(Date, nullable=True)
    prioridade = Column(String(20), nullable=False, default="media")
    status = Column(String(20), nullable=False, default="ativo")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_financial_goals_user_status", "user_id", "status"), Index("ix_financial_goals_org_status", "organization_id", "status"),)


class MonthlyFinancialTarget(Base):
    __tablename__ = "monthly_financial_targets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    renda_prevista = Column(Float, nullable=False, default=0.0)
    despesa_limite = Column(Float, nullable=False, default=0.0)
    economia_meta = Column(Float, nullable=False, default=0.0)
    investimento_meta = Column(Float, nullable=False, default=0.0)
    reserva_meta = Column(Float, nullable=False, default=0.0)
    observacao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_monthly_financial_targets_user_month"),
        Index("ix_monthly_financial_targets_user_period", "user_id", "year", "month"),
    )


class FinancialMonthlyReport(Base):
    __tablename__ = "financial_monthly_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    classification = Column(String(20), nullable=False)
    diagnosis_text = Column(Text, nullable=False)
    income = Column(Float, nullable=False, default=0.0)
    expenses = Column(Float, nullable=False, default=0.0)
    monthly_balance = Column(Float, nullable=False, default=0.0)
    emergency_reserve = Column(Float, nullable=False, default=0.0)
    reserve_months = Column(Float, nullable=False, default=0.0)
    payload_json = Column(JSON, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_financial_monthly_reports_user_month"),
        Index("ix_financial_monthly_reports_user_period", "user_id", "year", "month"),
    )


class FinancialDecisionHistory(Base):
    """Histórico incremental das decisões analisadas pelo consultor financeiro."""

    __tablename__ = "financial_decision_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    decision_type = Column(String(40), index=True, nullable=False)
    classification = Column(String(20), index=True, nullable=False)
    decision = Column(String(40), nullable=False)
    income = Column(Float, nullable=False, default=0.0)
    expenses = Column(Float, nullable=False, default=0.0)
    monthly_balance = Column(Float, nullable=False, default=0.0)
    emergency_reserve = Column(Float, nullable=False, default=0.0)
    monthly_payment = Column(Float, nullable=True)
    payload_json = Column(JSON, nullable=False)
    diagnosis_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_financial_decision_history_user_created", "user_id", "created_at"),
        Index("ix_financial_decision_history_user_type", "user_id", "decision_type"),
    )

from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.database import Base


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    monthly_income = Column(Float, nullable=False, default=0.0)
    monthly_expenses = Column(Float, nullable=False, default=0.0)
    available_to_invest = Column(Float, nullable=False, default=0.0)
    emergency_reserve_months = Column(Float, nullable=False, default=0.0)
    risk_profile = Column(String(40), nullable=False, default="moderate")
    investment_experience = Column(String(40), nullable=False, default="beginner")
    financial_goal = Column(String(120), nullable=True)
    target_amount = Column(Float, nullable=True)
    target_date = Column(Date, nullable=True)
    preferred_markets = Column(Text, nullable=True)  # JSON list: equities, fiis, etfs, bdrs, crypto, fixed_income, cash
    liquidity_preference = Column(String(40), nullable=False, default="medium")
    dividend_preference = Column(String(40), nullable=False, default="medium")
    volatility_tolerance = Column(String(40), nullable=False, default="medium")
    investment_horizon = Column(String(40), nullable=False, default="medium_term")
    monthly_investment_capacity = Column(Float, nullable=False, default=0.0)
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_financial_profiles_org_user"),
        Index("ix_financial_profiles_org_deleted", "organization_id", "deleted_at"),
    )


class IntelligentRecommendationSnapshot(Base):
    __tablename__ = "intelligent_recommendation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    financial_profile_id = Column(Integer, nullable=True, index=True)
    recommendation_json = Column(Text, nullable=False)
    disclaimer = Column(Text, nullable=False)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_recommendation_snapshots_org_created", "organization_id", "created_at"),)


class FinancialGoalEngine(Base):
    __tablename__ = "financial_goals_engine"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    goal_type = Column(String(60), nullable=False, default="custom")
    target_amount = Column(Float, nullable=False, default=0.0)
    current_amount = Column(Float, nullable=False, default=0.0)
    target_date = Column(Date, nullable=True)
    monthly_contribution = Column(Float, nullable=False, default=0.0)
    inflation_adjusted_target = Column(Float, nullable=False, default=0.0)
    risk_profile = Column(String(40), nullable=False, default="moderate")
    investment_horizon = Column(String(40), nullable=False, default="medium_term")
    success_probability = Column(Float, nullable=False, default=0.0)
    estimated_completion_date = Column(Date, nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_financial_goals_engine_org_user", "organization_id", "user_id"),
        Index("ix_financial_goals_engine_org_deleted", "organization_id", "deleted_at"),
    )


class BudgetAdvisorSnapshot(Base):
    __tablename__ = "budget_advisor_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    recommended_model = Column(String(60), nullable=False)
    health_score = Column(Integer, nullable=False, default=0)
    investment_capacity = Column(Float, nullable=False, default=0.0)
    payload_json = Column(Text, nullable=False)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_budget_advisor_snapshots_org_period", "organization_id", "year", "month"),
    )


class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    financial_literacy_level = Column(String(40), nullable=False, default="beginner")
    preferred_tone = Column(String(40), nullable=False, default="consultive")
    preferred_detail_level = Column(String(40), nullable=False, default="short")
    observed_risk_behavior = Column(String(40), nullable=False, default="balanced")
    recurring_challenges = Column(Text, nullable=False, default="[]")
    engagement_score = Column(Integer, nullable=False, default=50)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_user_learning_profiles_org_user"),
        Index("ix_user_learning_profiles_org_user", "organization_id", "user_id"),
    )


class AdvisorConversation(Base):
    __tablename__ = "advisor_conversations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(160), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_advisor_conversations_org_user", "organization_id", "user_id"),)


class AdvisorMessage(Base):
    __tablename__ = "advisor_messages"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    role = Column(String(24), nullable=False)
    intent = Column(String(80), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_advisor_messages_org_user_created", "organization_id", "user_id", "created_at"),)


class AdvisorMemorySummary(Base):
    __tablename__ = "advisor_memory_summaries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    summary_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "user_id", "conversation_id", name="uq_advisor_memory_org_user_conversation"),)


class AIAdvisorUsageLog(Base):
    __tablename__ = "ai_advisor_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    question_hash = Column(String(64), nullable=False)
    topic = Column(String(80), nullable=False, default="general")
    intent = Column(String(80), nullable=False, default="open_financial_guidance")
    provider = Column(String(40), nullable=False, default="local_fallback")
    success = Column(Boolean, nullable=False, default=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    feedback = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_ai_advisor_usage_org_created", "organization_id", "created_at"),)

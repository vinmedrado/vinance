from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from backend.app.database import Base


class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), index=True, nullable=False)
    ticker = Column(String(32), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    asset_class = Column(String(32), index=True, nullable=False)
    currency = Column(String(16), default="BRL", nullable=False)
    source = Column(String(64), nullable=True)
    country = Column(String(64), default="BR", nullable=False)
    last_updated_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("symbol", "asset_class", name="uq_assets_symbol_class"),
        UniqueConstraint("ticker", "asset_class", name="uq_assets_ticker_class"),
    )


class AssetPrice(Base):
    __tablename__ = "asset_prices"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), index=True, nullable=True)
    symbol = Column(String(32), index=True, nullable=False)
    date = Column(DateTime(timezone=True), index=True, nullable=False)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    source = Column(String(64), nullable=True)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("symbol", "date", "source", name="uq_asset_prices_symbol_date_source"),)


class AssetFundamental(Base):
    __tablename__ = "asset_fundamentals"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), index=True, nullable=True)
    symbol = Column(String(32), index=True, nullable=False)
    pe_ratio = Column(Float, nullable=True)
    price_to_book = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    source = Column(String(64), nullable=True)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    date = Column(DateTime(timezone=True), index=True, nullable=False)
    value = Column(Float, nullable=True)
    source = Column(String(64), default="BCB_SGS", nullable=False)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvestmentOpportunity(Base):
    __tablename__ = "investment_opportunities"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    symbol = Column(String(32), index=True, nullable=False)
    asset_class = Column(String(32), index=True, nullable=False)
    score = Column(Float, nullable=False)
    classification = Column(String(32), nullable=False)
    metrics_json = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (Index("ix_investment_opportunities_user_created", "user_id", "created_at"),)


class InvestmentAnalysisHistory(Base):
    __tablename__ = "investment_analysis_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    risk_profile = Column(String(32), nullable=False)
    allocation_json = Column(JSON, nullable=True)
    top_opportunities_json = Column(JSON, nullable=True)
    macro_context_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (Index("ix_investment_history_user_created", "user_id", "created_at"),)


class UserInvestmentPreference(Base):
    __tablename__ = "user_investment_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, unique=True, nullable=False)
    risk_profile = Column(String(32), default="Moderado", nullable=False)
    preferred_asset_classes = Column(JSON, nullable=True)
    excluded_symbols = Column(JSON, nullable=True)
    max_crypto_pct = Column(Float, default=0.10, nullable=False)
    max_single_asset_pct = Column(Float, default=0.15, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MarketIndex(Base):
    __tablename__ = "market_indices"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), index=True, nullable=False)
    name = Column(String(128), nullable=False)
    date = Column(DateTime(timezone=True), index=True, nullable=False)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    source = Column(String(64), default="yfinance", nullable=False)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("symbol", "date", "source", name="uq_market_indices_symbol_date_source"),)

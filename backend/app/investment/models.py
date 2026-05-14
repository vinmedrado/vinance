from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.sql import func

from backend.app.database import Base


class AssetDividend(Base):
    __tablename__ = "asset_dividends"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), index=True, nullable=True)
    symbol = Column(String(32), index=True, nullable=False)
    date = Column(DateTime(timezone=True), index=True, nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(16), default="BRL", nullable=False)
    source = Column(String(64), default="yfinance", nullable=False)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "date", "amount", "source", name="uq_asset_dividends_symbol_date_amount_source"),
        Index("ix_asset_dividends_symbol_date", "symbol", "date"),
    )


class FixedIncomeProduct(Base):
    __tablename__ = "fixed_income_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    issuer = Column(String(160), nullable=False)
    product_type = Column(String(40), index=True, nullable=False)  # Tesouro, CDB, LCI, LCA
    name = Column(String(220), nullable=False)
    indexer = Column(String(40), nullable=False)  # CDI, IPCA, PRE, SELIC
    rate = Column(Float, nullable=False, default=0.0)
    maturity_date = Column(DateTime(timezone=True), nullable=True)
    liquidity_days = Column(Integer, nullable=False, default=0)
    guarantee_type = Column(String(80), nullable=True)
    minimum_investment = Column(Float, nullable=False, default=0.0)
    source = Column(String(64), default="csv_manual", nullable=False)
    currency = Column(String(16), default="BRL", nullable=False)
    raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "issuer", "product_type", "name", "maturity_date", name="uq_fixed_income_user_product"),
        Index("ix_fixed_income_user_type", "user_id", "product_type"),
    )


class DataSyncLog(Base):
    __tablename__ = "data_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), index=True, nullable=False)
    entity = Column(String(120), index=True, nullable=False)
    status = Column(String(30), index=True, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    rows_inserted = Column(Integer, nullable=False, default=0)
    rows_updated = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)

    __table_args__ = (Index("ix_data_sync_logs_source_entity", "source", "entity"),)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), index=True, nullable=True)
    symbol = Column(String(32), index=True, nullable=False)
    asset_class = Column(String(32), index=True, nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    average_price = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=True)
    currency = Column(String(16), default="BRL", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_portfolio_positions_user_symbol", "user_id", "symbol"),)

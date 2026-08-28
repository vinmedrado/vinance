from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class AssetCatalog(Base):
    __tablename__ = "asset_catalog"
    __table_args__ = (
        UniqueConstraint("ticker", "market", name="uq_asset_catalog_ticker_market"),
        Index("ix_asset_catalog_market", "market"),
        Index("ix_asset_catalog_ticker", "ticker"),
        Index("ix_asset_catalog_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    segment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="BRL")
    exchange: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

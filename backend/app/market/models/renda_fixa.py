from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class RendaFixaProduto(Base):
    __tablename__ = "renda_fixa_produtos"
    __table_args__ = (
        UniqueConstraint("nome", "emissor", "tipo", "vencimento", "source", name="uq_renda_fixa_produtos_identity"),
        UniqueConstraint("source", "source_product_id", name="uq_renda_fixa_produtos_source_product"),
        CheckConstraint("currency = upper(currency)", name="ck_renda_fixa_produtos_currency_upper"),
        CheckConstraint("unit_price IS NULL OR unit_price > 0", name="ck_renda_fixa_produtos_unit_price_positive"),
        CheckConstraint("redemption_unit_price IS NULL OR redemption_unit_price > 0", name="ck_renda_fixa_produtos_redemption_price_positive"),
        CheckConstraint("base_unit_price IS NULL OR base_unit_price > 0", name="ck_renda_fixa_produtos_base_price_positive"),
        CheckConstraint("investimento_minimo IS NULL OR investimento_minimo >= 0", name="ck_renda_fixa_produtos_minimum_nonnegative"),
        Index("ix_renda_fixa_produtos_tipo", "tipo"),
        Index("ix_renda_fixa_produtos_indexador", "indexador"),
        Index("ix_renda_fixa_produtos_is_active", "is_active"),
        Index("ix_renda_fixa_produtos_coletado_em", "coletado_em"),
        Index("ix_renda_fixa_produtos_asset_catalog_id", "asset_catalog_id"),
        Index("ix_renda_fixa_produtos_market_date", "market_date"),
        Index("ix_renda_fixa_produtos_active_market_date", "is_active", "market_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_product_id: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_catalog_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_catalog.id", ondelete="SET NULL"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    emissor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    indexador: Mapped[str | None] = mapped_column(String(80), nullable=True)
    taxa_juros: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    taxa_total_equiv: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    rate_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purchase_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    redemption_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    redemption_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    base_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    liquidez_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liquidity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    investimento_minimo: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    garantia_fgc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guarantee_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tax_treatment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    codigo_tesouro: Mapped[str | None] = mapped_column(String(80), nullable=True)
    selic_vigente: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ipca_12m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    market_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

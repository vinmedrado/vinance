from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class RendaFixaProduto(Base):
    __tablename__ = "renda_fixa_produtos"
    __table_args__ = (
        UniqueConstraint("nome", "emissor", "tipo", "vencimento", "source", name="uq_renda_fixa_produtos_identity"),
        Index("ix_renda_fixa_produtos_tipo", "tipo"),
        Index("ix_renda_fixa_produtos_indexador", "indexador"),
        Index("ix_renda_fixa_produtos_is_active", "is_active"),
        Index("ix_renda_fixa_produtos_coletado_em", "coletado_em"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    emissor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    indexador: Mapped[str | None] = mapped_column(String(80), nullable=True)
    taxa_juros: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    taxa_total_equiv: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    liquidez_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    investimento_minimo: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    garantia_fgc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    codigo_tesouro: Mapped[str | None] = mapped_column(String(80), nullable=True)
    selic_vigente: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ipca_12m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

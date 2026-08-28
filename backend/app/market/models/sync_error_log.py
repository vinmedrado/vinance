from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SyncErrorLog(Base):
    __tablename__ = "sync_error_log"
    __table_args__ = (
        Index("ix_sync_error_log_run_id", "run_id"),
        Index("ix_sync_error_log_mercado", "mercado"),
        Index("ix_sync_error_log_ticker", "ticker"),
        Index("ix_sync_error_log_tipo_erro", "tipo_erro"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mercado: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    tipo_erro: Mapped[str] = mapped_column(String(32), nullable=False)
    erro: Mapped[str] = mapped_column(Text, nullable=False)
    segundos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    processado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

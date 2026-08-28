from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SyncLog(Base):
    __tablename__ = "sync_log"
    __table_args__ = (
        Index("ix_sync_log_run_id", "run_id"),
        Index("ix_sync_log_source", "source"),
        Index("ix_sync_log_mercado", "mercado"),
        Index("ix_sync_log_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    mercado: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sucesso_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tempo_segundos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

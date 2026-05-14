from __future__ import annotations

from sqlalchemy.orm import declarative_base

from db.database import SessionLocal, get_sync_session, sync_engine

Base = declarative_base()

def get_db():
    yield from get_sync_session()

def init_db() -> None:
    # Importa modelos para registrar metadata sem executar lógica de domínio.
    import backend.app.models  # noqa: F401
    try:
        Base.metadata.create_all(bind=sync_engine)
    except Exception:
        # Em produção com Alembic, falhas de conexão no startup não devem impedir import/testes.
        pass

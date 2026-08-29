"""LEGACY SYNCHRONOUS SQLALCHEMY COMPATIBILITY ONLY.

The VinanceOS runtime is asynchronous and new modules must use
``backend.app.core.database``. This module exists only for the small set of
legacy consumers that still require a synchronous SQLAlchemy ``Session``.

It derives the synchronous driver URL from the official application setting,
creates the engine lazily, owns no declarative metadata, and never creates or
migrates schema. Importing it does not open a connection or run a query.

The canonical declarative base remains ``backend.app.core.database.Base``.
The context managers below deliberately do not commit automatically: legacy
callers retain explicit transaction ownership.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from threading import RLock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

_SYNC_DRIVER = "postgresql+psycopg2"
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_initialization_lock = RLock()


def get_sync_database_url() -> URL:
    """Return the official database URL with only its SQLAlchemy driver changed."""

    configured_url = make_url(settings.database_url)
    if configured_url.get_backend_name() != "postgresql":
        raise RuntimeError("Legacy synchronous access supports the official PostgreSQL database only.")
    return configured_url.set(drivername=_SYNC_DRIVER)


def is_sync_engine_initialized() -> bool:
    """Report whether a consumer has initialized the lazy synchronous engine."""

    return _engine is not None


def get_sync_engine() -> Engine:
    """Return the process-local lazy engine for legacy synchronous consumers."""

    global _engine
    if _engine is None:
        with _initialization_lock:
            if _engine is None:
                _engine = create_engine(
                    get_sync_database_url(),
                    echo=settings.debug,
                    pool_pre_ping=True,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    future=True,
                )
    return _engine


def _get_sync_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        with _initialization_lock:
            if _session_factory is None:
                _session_factory = sessionmaker(
                    bind=get_sync_engine(),
                    class_=Session,
                    autoflush=False,
                    expire_on_commit=False,
                    autocommit=False,
                )
    return _session_factory


def create_sync_session() -> Session:
    """Create a legacy synchronous session; its caller must close it."""

    return _get_sync_session_factory()()


def get_sync_session() -> Generator[Session, None, None]:
    """FastAPI-compatible dependency with rollback and guaranteed close."""

    session = create_sync_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def sync_session() -> Iterator[Session]:
    """Yield a session, rolling back exceptions and always returning its connection."""

    session = create_sync_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_sync_database() -> None:
    """Dispose the lazy pool when explicitly requested by tests or process shutdown."""

    global _engine, _session_factory
    with _initialization_lock:
        engine = _engine
        _session_factory = None
        _engine = None
    if engine is not None:
        engine.dispose()

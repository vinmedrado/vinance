from __future__ import annotations

import asyncio
import importlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from backend.app.core import sync_database
from backend.app.core.config import settings


@pytest.fixture(autouse=True)
def _isolated_sync_engine():
    sync_database.dispose_sync_database()
    yield
    sync_database.dispose_sync_database()


def test_isolated_import_has_no_engine_or_database_side_effect() -> None:
    script = """
from backend.app.core import sync_database
assert sync_database.is_sync_engine_initialized() is False
assert 'Base' not in sync_database.__dict__
assert 'metadata' not in sync_database.__dict__
assert 'SessionLocal' not in sync_database.__dict__
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sync_url_reuses_the_official_configuration() -> None:
    official = make_url(settings.database_url)
    synchronous = sync_database.get_sync_database_url()

    assert synchronous.drivername == "postgresql+psycopg2"
    assert synchronous.get_backend_name() == official.get_backend_name() == "postgresql"
    assert synchronous.username == official.username
    assert synchronous.password == official.password
    assert synchronous.host == official.host
    assert synchronous.port == official.port
    assert synchronous.database == official.database
    assert synchronous.query == official.query


def test_sync_url_rejects_a_non_postgresql_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", "sqlite:///legacy.db")

    with pytest.raises(RuntimeError, match="official PostgreSQL database"):
        sync_database.get_sync_database_url()


def test_engine_is_lazy_and_initialized_once_across_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class FakeEngine:
        def dispose(self) -> None:
            return None

    fake_engine = FakeEngine()

    def fake_create_engine(*args, **kwargs):
        calls.append((args, kwargs))
        return fake_engine

    monkeypatch.setattr(sync_database, "create_engine", fake_create_engine)
    assert sync_database.is_sync_engine_initialized() is False

    with ThreadPoolExecutor(max_workers=8) as executor:
        engines = list(executor.map(lambda _: sync_database.get_sync_engine(), range(32)))

    assert calls and len(calls) == 1
    assert all(engine is fake_engine for engine in engines)
    assert sync_database.is_sync_engine_initialized() is True


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_context_manager_leaves_commit_explicit_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(sync_database, "create_sync_session", lambda: session)

    with sync_database.sync_session() as yielded:
        assert yielded is session

    assert session.committed is False
    assert session.rolled_back is False
    assert session.closed is True


def test_context_manager_rolls_back_and_closes_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(sync_database, "create_sync_session", lambda: session)

    with pytest.raises(RuntimeError, match="expected failure"):
        with sync_database.sync_session():
            raise RuntimeError("expected failure")

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_dependency_rolls_back_and_closes_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(sync_database, "create_sync_session", lambda: session)
    dependency = sync_database.get_sync_session()

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="dependency failure"):
        dependency.throw(RuntimeError("dependency failure"))

    assert session.rolled_back is True
    assert session.closed is True


def _pool_checked_out() -> int:
    return sync_database.get_sync_engine().pool.checkedout()


def test_real_session_select_commit_rollback_and_recovery() -> None:
    engine = sync_database.get_sync_engine()
    baseline = engine.pool.checkedout()

    with sync_database.sync_session() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        assert session.in_transaction() is True
        session.commit()
        assert session.in_transaction() is False

        with pytest.raises(DBAPIError):
            session.execute(text("SELECT 1 / 0")).scalar_one()
        session.rollback()
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        session.rollback()

    assert engine.pool.checkedout() == baseline


def test_creating_and_closing_a_session_does_not_checkout_a_connection() -> None:
    engine = sync_database.get_sync_engine()
    baseline = engine.pool.checkedout()

    session = sync_database.create_sync_session()
    assert engine.pool.checkedout() == baseline
    session.close()

    assert engine.pool.checkedout() == baseline


def test_multiple_real_sessions_are_independent_and_return_connections() -> None:
    engine = sync_database.get_sync_engine()
    baseline = engine.pool.checkedout()
    first = sync_database.create_sync_session()
    second = sync_database.create_sync_session()

    try:
        assert first.execute(text("SELECT 1")).scalar_one() == 1
        assert second.execute(text("SELECT 2")).scalar_one() == 2
        assert engine.pool.checkedout() == baseline + 2
        first.rollback()
        second.rollback()
    finally:
        first.close()
        second.close()

    assert engine.pool.checkedout() == baseline


def test_sync_and_async_sessions_coexist_on_the_same_database() -> None:
    from backend.app.core.database import AsyncSessionLocal, engine as async_engine

    def query_synchronously() -> str:
        with sync_database.sync_session() as session:
            return session.execute(text("SELECT current_database()")).scalar_one()

    async def exercise_both_drivers() -> tuple[str, str]:
        async with AsyncSessionLocal() as session:
            async_name = (await session.execute(text("SELECT current_database()"))).scalar_one()
            sync_name = await asyncio.to_thread(query_synchronously)
            await session.rollback()
        return async_name, sync_name

    async_name, sync_name = asyncio.run(exercise_both_drivers())
    assert async_name == sync_name == make_url(settings.database_url).database
    assert async_engine.url.drivername == "postgresql+asyncpg"
    assert sync_database.get_sync_engine().url.drivername == "postgresql+psycopg2"
    assert _pool_checked_out() == 0


def test_read_only_use_does_not_change_the_public_schema() -> None:
    table_query = text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)

    with sync_database.sync_session() as session:
        before = tuple(session.execute(table_query).scalars())
        session.rollback()

    with sync_database.sync_session() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        session.commit()

    with sync_database.sync_session() as session:
        after = tuple(session.execute(table_query).scalars())
        session.rollback()

    assert after == before


def test_dispose_releases_the_pool_and_allows_clean_reinitialization() -> None:
    first_engine = sync_database.get_sync_engine()
    with sync_database.sync_session() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        session.rollback()

    sync_database.dispose_sync_database()
    assert sync_database.is_sync_engine_initialized() is False

    second_engine = sync_database.get_sync_engine()
    assert second_engine is not first_engine
    with sync_database.sync_session() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        session.rollback()
    assert second_engine.pool.checkedout() == 0


def test_only_schema_compatible_consumers_use_the_sync_layer() -> None:
    sync_database.dispose_sync_database()

    db_session_module = importlib.import_module("services.db_session")
    health_module = importlib.import_module("services.production_health_service")

    assert sync_database.is_sync_engine_initialized() is False
    with db_session_module.db_session() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        session.rollback()

    dependency = db_session_module.get_db()
    dependency_session = next(dependency)
    try:
        assert dependency_session.execute(text("SELECT 1")).scalar_one() == 1
        dependency_session.rollback()
    finally:
        dependency.close()

    assert health_module.check_postgres()["status"] == "pass"
    assert _pool_checked_out() == 0

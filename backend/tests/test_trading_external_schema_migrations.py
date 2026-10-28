from __future__ import annotations

from pathlib import Path

from backend.trading.storage.backup import TRADING_TABLES, _database_env
from backend.trading.storage.migrate import (
    LATEST_TRADING_SCHEMA_VERSION,
    REQUIRED_TABLES,
    migration_checksum,
    rollback,
)
from backend.trading.storage.migrations.revisions import MIGRATIONS
from backend.app.core.readiness import SchemaRevisionStatus


def test_external_schema_history_is_linear_and_checksummed() -> None:
    assert [item.version for item in MIGRATIONS] == [
        "0001_initial_research",
        "0002_assisted_paper_v1",
    ]
    assert LATEST_TRADING_SCHEMA_VERSION == "0002_assisted_paper_v1"
    checksums = [migration_checksum(item) for item in MIGRATIONS]
    assert len(set(checksums)) == len(checksums)
    assert all(len(value) == 64 for value in checksums)


def test_assisted_schema_enforces_personal_owner_and_paper_only() -> None:
    sql = "\n".join(MIGRATIONS[-1].upgrade_sql)
    assert "owner_user_id INTEGER NOT NULL REFERENCES users(id)" in sql
    assert "ownership_scope = 'PERSONAL'" in sql
    assert sql.count("paper_only IS TRUE") >= 4
    assert "uq_trading_paper_order_idempotency" in sql
    assert "fk_trading_paper_order_account_owner" in sql
    assert "fk_trading_paper_position_account_owner" in sql
    assert "trading_paper_events is append-only" in sql


def test_destructive_rollback_maps_new_signal_states_to_legacy_semantics() -> None:
    import inspect

    rollback_source = inspect.getsource(rollback)
    assert "BUY_CANDIDATE' THEN 'BUY" in rollback_source
    assert "AVOID' THEN 'HOLD" in rollback_source
    assert "0002_assisted_paper_v1" in rollback_source


def test_external_tables_stay_outside_main_alembic_ownership() -> None:
    ownership = Path("backend/alembic/schema_ownership.py").read_text(encoding="utf-8")
    for table in REQUIRED_TABLES.intersection(
        {
            "crypto_candles",
            "crypto_features",
            "crypto_targets",
            "trading_signals",
            "backtest_runs",
            "paper_trades",
        }
    ):
        assert table in ownership
    for table in REQUIRED_TABLES | {
        "trading_schema_version",
        "trading_schema_migrations",
    }:
        assert table in ownership


def test_backup_scope_is_allowlisted_and_connection_password_is_only_environmental() -> None:
    assert "users" not in TRADING_TABLES
    assert "households" not in TRADING_TABLES
    assert "financial_state_snapshots" not in TRADING_TABLES
    env = _database_env("postgresql://user:private-value@db.example:5433/vinance")
    assert env["PGPASSWORD"] == "private-value"
    assert env["PGDATABASE"] == "vinance"
    assert env["PGHOST"] == "db.example"


def test_application_readiness_fails_closed_on_external_schema_drift() -> None:
    assert not SchemaRevisionStatus(
        current="0027_auth_sessions",
        expected="0027_auth_sessions",
        trading_current=None,
    ).compatible
    assert SchemaRevisionStatus(
        current="0027_auth_sessions",
        expected="0027_auth_sessions",
        trading_current=LATEST_TRADING_SCHEMA_VERSION,
    ).compatible

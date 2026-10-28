from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import Connection, Engine, inspect, text

from .database import create_sync_engine
from .migrations.revisions import MIGRATIONS, Migration


LATEST_TRADING_SCHEMA_VERSION = MIGRATIONS[-1].version
MIGRATION_LOCK_NAME = "vinance-trading-external-schema"
VERSION_TABLE = "trading_schema_version"
HISTORY_TABLE = "trading_schema_migrations"
REQUIRED_TABLES = {
    "crypto_candles",
    "crypto_features",
    "crypto_targets",
    "trading_signals",
    "backtest_runs",
    "paper_trades",
    "trading_paper_accounts",
    "trading_paper_orders",
    "trading_paper_positions",
    "trading_paper_events",
}

# Structural checks make it impossible to "adopt" a partially compatible
# hand-created schema merely because the table names happen to exist.  The
# external runner owns these contracts independently from the main Alembic
# history and therefore must validate them itself.
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "crypto_candles": {
        "id", "exchange", "symbol", "interval", "open_time", "close_time",
        "open", "high", "low", "close", "volume", "quote_volume", "trades",
        "created_at", "updated_at",
    },
    "crypto_features": {"id", "candle_id", "feature_version", "features", "created_at"},
    "crypto_targets": {
        "id", "candle_id", "target_name", "horizon_candles", "threshold_pct",
        "target_value", "target_class", "created_at",
    },
    "trading_signals": {
        "id", "symbol", "interval", "signal_time", "model_version", "side",
        "probability", "score", "reason", "created_at", "prediction_id",
        "candle_id", "feature_version", "target_version", "target_name",
        "reference_price", "stop_price", "target_price",
        "freshness_expires_at", "guardrail_status", "paper_only",
    },
    "backtest_runs": {
        "id", "name", "strategy_version", "started_at", "finished_at",
        "parameters", "metrics", "status",
    },
    "paper_trades": {
        "id", "signal_id", "symbol", "side", "quantity", "entry_price",
        "exit_price", "entry_time", "exit_time", "fee_paid", "pnl", "status",
    },
    "trading_paper_accounts": {
        "id", "owner_user_id", "ownership_scope", "status", "quote_asset",
        "initial_virtual_balance", "cash", "equity", "realized_pnl",
        "unrealized_pnl", "peak_equity", "max_drawdown", "ruleset_version",
        "paper_only", "optimistic_version", "created_at", "updated_at",
    },
    "trading_paper_orders": {
        "id", "paper_account_id", "owner_user_id", "idempotency_key",
        "request_fingerprint", "correlation_id", "signal_id", "prediction_id",
        "symbol", "market", "interval", "side", "order_type", "quantity",
        "notional", "reference_price", "limit_price", "stop_price",
        "target_price", "fee_paid", "status", "model_version",
        "feature_version", "target_version", "risk_decision", "risk_snapshot",
        "financial_fingerprints", "paper_only", "optimistic_version",
        "created_at", "updated_at", "filled_at", "cancelled_at",
    },
    "trading_paper_positions": {
        "id", "paper_account_id", "owner_user_id", "symbol", "market",
        "interval", "side", "status", "quantity", "average_entry_price",
        "current_reference_price", "entry_fee", "realized_pnl",
        "unrealized_pnl", "stop_price", "target_price", "opening_order_id",
        "closing_order_id", "paper_only", "optimistic_version", "opened_at",
        "updated_at", "closed_at",
    },
    "trading_paper_events": {
        "id", "owner_user_id", "paper_account_id", "event_type", "signal_id",
        "prediction_id", "order_id", "position_id", "symbol", "event_payload",
        "decision_context", "risk_context", "correlation_id", "created_at",
    },
}

REQUIRED_NAMED_OBJECTS: dict[str, set[str]] = {
    "crypto_candles": {"uq_crypto_candle", "ck_crypto_candle_prices", "ix_crypto_candles_symbol_interval_time"},
    "crypto_features": {"uq_crypto_feature", "ix_crypto_features_version"},
    "crypto_targets": {"uq_crypto_target"},
    "trading_signals": {
        "ck_trading_signals_side", "ck_trading_signals_reference_price",
        "ck_trading_signals_stop_price", "ck_trading_signals_target_price",
        "ck_trading_signals_guardrail", "ck_trading_signals_paper_only",
        "uq_trading_signals_prediction_id", "ix_trading_signals_symbol_time",
        "ix_trading_signals_current_paper",
    },
    "trading_paper_accounts": {
        "uq_trading_paper_account_owner", "uq_trading_paper_account_id_owner",
        "ck_trading_paper_account_personal", "ck_trading_paper_account_status",
        "ck_trading_paper_account_quote", "ck_trading_paper_account_balances",
        "ck_trading_paper_account_paper_only", "ck_trading_paper_account_version",
        "ix_trading_paper_accounts_owner_status",
    },
    "trading_paper_orders": {
        "fk_trading_paper_order_account_owner", "uq_trading_paper_order_id_owner",
        "uq_trading_paper_order_idempotency", "ck_trading_paper_order_side",
        "ck_trading_paper_order_type", "ck_trading_paper_order_status",
        "ck_trading_paper_order_values", "ck_trading_paper_order_limit",
        "ck_trading_paper_order_paper_only", "ck_trading_paper_order_version",
        "ix_trading_paper_orders_owner_created", "ix_trading_paper_orders_account_status",
        "uq_trading_paper_order_signal_once",
    },
    "trading_paper_positions": {
        "fk_trading_paper_position_account_owner", "fk_trading_paper_position_open_order_owner",
        "fk_trading_paper_position_close_order_owner", "uq_trading_paper_position_open_order",
        "uq_trading_paper_position_id_owner", "ck_trading_paper_position_side",
        "ck_trading_paper_position_status", "ck_trading_paper_position_values",
        "ck_trading_paper_position_close_state", "ck_trading_paper_position_paper_only",
        "ck_trading_paper_position_version", "ix_trading_paper_positions_owner_status",
        "ix_trading_paper_positions_account_symbol",
    },
    "trading_paper_events": {
        "fk_trading_paper_event_account_owner", "fk_trading_paper_event_order_owner",
        "fk_trading_paper_event_position_owner", "ix_trading_paper_events_owner_created",
        "ix_trading_paper_events_correlation",
    },
}

REQUIRED_NOT_NULL_COLUMNS: dict[str, set[str]] = {
    "trading_signals": {"symbol", "interval", "signal_time", "model_version", "side", "guardrail_status", "paper_only"},
    "trading_paper_accounts": {"owner_user_id", "ownership_scope", "quote_asset", "cash", "equity", "paper_only", "optimistic_version"},
    "trading_paper_orders": {"paper_account_id", "owner_user_id", "idempotency_key", "request_fingerprint", "symbol", "side", "quantity", "notional", "reference_price", "paper_only"},
    "trading_paper_positions": {"paper_account_id", "owner_user_id", "symbol", "quantity", "average_entry_price", "paper_only"},
    "trading_paper_events": {"owner_user_id", "paper_account_id", "event_type", "event_payload", "decision_context", "risk_context", "correlation_id"},
}

REQUIRED_TYPE_PREFIXES: dict[str, dict[str, str]] = {
    "trading_signals": {
        "id": "BIGINT", "prediction_id": "VARCHAR", "reason": "JSONB",
        "reference_price": "NUMERIC", "freshness_expires_at": "TIMESTAMP",
        "paper_only": "BOOLEAN",
    },
    "trading_paper_accounts": {
        "id": "BIGINT", "owner_user_id": "INTEGER", "cash": "NUMERIC",
        "equity": "NUMERIC", "paper_only": "BOOLEAN",
        "optimistic_version": "INTEGER",
    },
    "trading_paper_orders": {
        "id": "BIGINT", "paper_account_id": "BIGINT", "owner_user_id": "INTEGER",
        "risk_snapshot": "JSONB", "financial_fingerprints": "JSONB",
        "paper_only": "BOOLEAN",
    },
    "trading_paper_positions": {
        "id": "BIGINT", "paper_account_id": "BIGINT", "owner_user_id": "INTEGER",
        "quantity": "NUMERIC", "paper_only": "BOOLEAN",
    },
    "trading_paper_events": {
        "id": "BIGINT", "paper_account_id": "BIGINT", "owner_user_id": "INTEGER",
        "event_payload": "JSONB", "decision_context": "JSONB", "risk_context": "JSONB",
    },
}


def migration_checksum(migration: Migration) -> str:
    payload = json.dumps(
        asdict(migration), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _has_table(connection: Connection, name: str) -> bool:
    return inspect(connection).has_table(name, schema="public")


def _bootstrap(connection: Connection) -> None:
    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS trading_schema_migrations (
            version VARCHAR(80) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS trading_schema_version (
            id SMALLINT PRIMARY KEY DEFAULT 1,
            version VARCHAR(80),
            checksum CHAR(64),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_trading_schema_version_singleton CHECK (id = 1)
        )
        """
    )
    connection.execute(
        text(
            """
            INSERT INTO trading_schema_version (id, version, checksum)
            VALUES (1, NULL, NULL)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def _read_applied(connection: Connection) -> list[dict[str, Any]]:
    if not _has_table(connection, HISTORY_TABLE):
        return []
    rows = connection.execute(
        text(
            "SELECT version, name, checksum, applied_at "
            "FROM trading_schema_migrations ORDER BY applied_at, version"
        )
    ).mappings()
    return [dict(row) for row in rows]


def _read_current(connection: Connection) -> str | None:
    if not _has_table(connection, VERSION_TABLE):
        return None
    return connection.execute(
        text("SELECT version FROM trading_schema_version WHERE id = 1")
    ).scalar_one_or_none()


def _schema_issues(connection: Connection, tables: set[str]) -> list[str]:
    inspector = inspect(connection)
    issues: list[str] = []
    for table, required_columns in REQUIRED_COLUMNS.items():
        if table not in tables:
            continue
        columns = {str(item["name"]): item for item in inspector.get_columns(table)}
        for column in sorted(required_columns.difference(columns)):
            issues.append(f"MISSING_COLUMN:{table}.{column}")
        for column in sorted(REQUIRED_NOT_NULL_COLUMNS.get(table, set())):
            metadata = columns.get(column)
            if metadata is not None and metadata.get("nullable") is not False:
                issues.append(f"NULLABLE_COLUMN:{table}.{column}")
        for column, expected_prefix in REQUIRED_TYPE_PREFIXES.get(table, {}).items():
            metadata = columns.get(column)
            if metadata is None:
                continue
            actual_type = str(metadata.get("type") or "").upper()
            if not actual_type.startswith(expected_prefix):
                issues.append(
                    f"INVALID_COLUMN_TYPE:{table}.{column}:{actual_type}"
                )

        primary_key = inspector.get_pk_constraint(table).get("constrained_columns") or []
        if primary_key != ["id"]:
            issues.append(f"INVALID_PRIMARY_KEY:{table}")

        named_objects: set[str] = set()
        for getter in (
            inspector.get_unique_constraints,
            inspector.get_foreign_keys,
            inspector.get_check_constraints,
            inspector.get_indexes,
        ):
            for item in getter(table):
                if item.get("name"):
                    named_objects.add(str(item["name"]))
        for name in sorted(REQUIRED_NAMED_OBJECTS.get(table, set()) - named_objects):
            issues.append(f"MISSING_SCHEMA_OBJECT:{table}.{name}")

    if "trading_paper_events" in tables:
        immutable_trigger = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_trigger trigger
                    JOIN pg_class relation ON relation.oid = trigger.tgrelid
                    JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = 'public'
                      AND relation.relname = 'trading_paper_events'
                      AND trigger.tgname = 'trg_trading_paper_events_immutable'
                      AND NOT trigger.tgisinternal
                )
                """
            )
        ).scalar_one()
        if not immutable_trigger:
            issues.append("MISSING_IMMUTABILITY_TRIGGER:trading_paper_events")
    return issues


def _audit(connection: Connection) -> dict[str, Any]:
    applied = _read_applied(connection)
    current = _read_current(connection)
    expected_versions = [migration.version for migration in MIGRATIONS]
    expected_by_version = {migration.version: migration for migration in MIGRATIONS}
    applied_versions = [str(row["version"]) for row in applied]
    issues: list[str] = []

    unknown = [version for version in applied_versions if version not in expected_by_version]
    if unknown:
        issues.append("UNKNOWN_MIGRATIONS:" + ",".join(unknown))
    known_applied = [version for version in applied_versions if version in expected_by_version]
    if known_applied != expected_versions[: len(known_applied)]:
        issues.append("NON_LINEAR_MIGRATION_HISTORY")
    for row in applied:
        migration = expected_by_version.get(str(row["version"]))
        if migration and str(row["checksum"]) != migration_checksum(migration):
            issues.append(f"CHECKSUM_MISMATCH:{migration.version}")
    expected_current = known_applied[-1] if known_applied else None
    if current != expected_current:
        issues.append("VERSION_POINTER_MISMATCH")

    pending = [
        version for version in expected_versions if version not in set(applied_versions)
    ]
    tables = set(inspect(connection).get_table_names(schema="public"))
    missing_tables = sorted(REQUIRED_TABLES.difference(tables))
    schema_issues = _schema_issues(connection, tables)
    at_latest = current == LATEST_TRADING_SCHEMA_VERSION and not pending
    compatible = at_latest and not issues and not missing_tables and not schema_issues
    return {
        "current": current,
        "latest": LATEST_TRADING_SCHEMA_VERSION,
        "applied": applied_versions,
        "pending": pending,
        "issues": issues,
        "schema_issues": schema_issues,
        "missing_tables": missing_tables,
        "compatible": compatible,
    }


def status(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        return _audit(connection)


def _assert_safe_history(state: dict[str, Any]) -> None:
    if state["issues"]:
        raise RuntimeError(
            "Trading schema history is incompatible: " + "; ".join(state["issues"])
        )


def upgrade(engine: Engine) -> dict[str, Any]:
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
            {"name": MIGRATION_LOCK_NAME},
        )
        _bootstrap(connection)
        state = _audit(connection)
        _assert_safe_history(state)
        applied = set(state["applied"])
        for migration in MIGRATIONS:
            if migration.version in applied:
                continue
            for statement in migration.upgrade_sql:
                connection.exec_driver_sql(statement)
            checksum = migration_checksum(migration)
            connection.execute(
                text(
                    """
                    INSERT INTO trading_schema_migrations (version, name, checksum)
                    VALUES (:version, :name, :checksum)
                    """
                ),
                {
                    "version": migration.version,
                    "name": migration.name,
                    "checksum": checksum,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE trading_schema_version
                    SET version = :version, checksum = :checksum, updated_at = NOW()
                    WHERE id = 1
                    """
                ),
                {"version": migration.version, "checksum": checksum},
            )
        result = _audit(connection)
        if not result["compatible"]:
            raise RuntimeError(
                "Trading schema upgrade did not reach a compatible state: "
                + json.dumps(result, sort_keys=True, default=str)
            )
        return result


def rollback(engine: Engine, *, allow_destructive: bool = False) -> dict[str, Any]:
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
            {"name": MIGRATION_LOCK_NAME},
        )
        if not _has_table(connection, HISTORY_TABLE):
            raise RuntimeError("Trading schema has no version history to roll back")
        state = _audit(connection)
        _assert_safe_history(state)
        if not state["applied"]:
            raise RuntimeError("Trading schema is already at base")
        current = str(state["applied"][-1])
        migration = next(item for item in MIGRATIONS if item.version == current)
        if migration.destructive_down and not allow_destructive:
            raise RuntimeError(
                f"Rollback {current} is destructive; pass --allow-destructive only on an isolated verified target"
            )
        if current == "0002_assisted_paper_v1":
            # Revision 0002 is already present in canonical databases, so its
            # checksummed SQL must remain immutable.  A destructive rollback
            # explicitly reduces the new signal vocabulary to the closest
            # legacy semantics before VARCHAR(10) is restored.
            connection.exec_driver_sql(
                "UPDATE trading_signals "
                "SET side = CASE "
                "WHEN side = 'BUY_CANDIDATE' THEN 'BUY' "
                "WHEN side = 'AVOID' THEN 'HOLD' "
                "ELSE side END "
                "WHERE side IN ('BUY_CANDIDATE', 'AVOID')"
            )
        for statement in migration.downgrade_sql:
            connection.exec_driver_sql(statement)
        connection.execute(
            text("DELETE FROM trading_schema_migrations WHERE version = :version"),
            {"version": current},
        )
        remaining = [item for item in MIGRATIONS if item.version != current]
        applied_remaining = [
            item for item in remaining if item.version in set(state["applied"][:-1])
        ]
        previous = applied_remaining[-1] if applied_remaining else None
        connection.execute(
            text(
                """
                UPDATE trading_schema_version
                SET version = :version, checksum = :checksum, updated_at = NOW()
                WHERE id = 1
                """
            ),
            {
                "version": previous.version if previous else None,
                "checksum": migration_checksum(previous) if previous else None,
            },
        )
        return _audit(connection)


def check(engine: Engine) -> dict[str, Any]:
    state = status(engine)
    if not state["compatible"]:
        raise RuntimeError(
            "Trading schema check failed: "
            + json.dumps(state, sort_keys=True, default=str)
        )
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Version the external Trading V2 schema")
    parser.add_argument("command", choices=("status", "upgrade", "rollback", "check"))
    parser.add_argument("--allow-destructive", action="store_true")
    args = parser.parse_args()
    engine = create_sync_engine()
    try:
        if args.command == "status":
            result = status(engine)
        elif args.command == "upgrade":
            result = upgrade(engine)
        elif args.command == "rollback":
            result = rollback(engine, allow_destructive=args.allow_destructive)
        else:
            result = check(engine)
    finally:
        engine.dispose()
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

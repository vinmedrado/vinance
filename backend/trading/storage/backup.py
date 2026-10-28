from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import inspect, text

from .database import create_sync_engine
from .migrate import check as check_schema


TRADING_TABLES = (
    "trading_schema_version",
    "trading_schema_migrations",
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
)
TRADING_DATA_TABLES = tuple(
    table
    for table in TRADING_TABLES
    if table not in {"trading_schema_version", "trading_schema_migrations"}
)


def _database_env(database_url: str) -> dict[str, str]:
    clean = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    clean = clean.replace("postgresql+psycopg2://", "postgresql://", 1)
    clean = clean.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(clean)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError("Trading backup requires a PostgreSQL DATABASE_URL")
    database = parsed.path.lstrip("/")
    if not database:
        raise RuntimeError("DATABASE_URL has no database name")
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": parsed.hostname,
            "PGPORT": str(parsed.port or 5432),
            "PGDATABASE": unquote(database),
            "PGUSER": unquote(parsed.username or ""),
            "PGPASSWORD": unquote(parsed.password or ""),
        }
    )
    return env


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"{name} is required for Trading backup operations")
    return resolved


def _run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_tables(database_url: str) -> list[str]:
    engine = create_sync_engine(database_url)
    try:
        names = set(inspect(engine).get_table_names(schema="public"))
    finally:
        engine.dispose()
    return [name for name in TRADING_TABLES if name in names]


def archive_inventory(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError("Trading backup archive is missing or empty")
    result = subprocess.run(
        [_tool("pg_restore"), "--list", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    toc = result.stdout
    tables = sorted(
        name for name in TRADING_DATA_TABLES if f" public {name} " in toc
    )
    table_data = sorted(
        name
        for name in TRADING_DATA_TABLES
        if f"TABLE DATA public {name} " in toc
    )
    if not tables:
        raise RuntimeError("Archive does not contain Trading tables")
    missing_table_data = sorted(set(tables).difference(table_data))
    if missing_table_data:
        raise RuntimeError(
            "Archive is missing Trading TABLE DATA entries: "
            + ", ".join(missing_table_data)
        )
    return {
        "archive": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "tables": tables,
        "table_data": table_data,
        "table_data_complete": True,
    }


def create_backup(*, database_url: str, output: Path) -> dict[str, object]:
    if output.exists():
        raise RuntimeError("Refusing to overwrite an existing Trading backup")
    tables = [
        table for table in _existing_tables(database_url) if table in TRADING_DATA_TABLES
    ]
    if not tables:
        raise RuntimeError("No Trading tables exist in the source database")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        _tool("pg_dump"),
        "--format=custom",
        "--data-only",
        "--no-owner",
        "--no-acl",
        "--file",
        str(output),
    ]
    for table in tables:
        command.extend(["--table", f"public.{table}"])
    try:
        _run(command, env=_database_env(database_url))
        inventory = archive_inventory(output)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(
        f"{inventory['sha256']}  {output.name}\n", encoding="ascii"
    )
    return {**inventory, "checksum_file": str(checksum_path.resolve())}


def restore_backup(
    *, database_url: str, archive: Path, confirm_isolated_target: bool
) -> dict[str, object]:
    if not confirm_isolated_target:
        raise RuntimeError("Restore requires --confirm-isolated-target")
    inventory = archive_inventory(archive)
    engine = create_sync_engine(database_url)
    try:
        existing = set(inspect(engine).get_table_names(schema="public"))
        missing = sorted(set(TRADING_TABLES).difference(existing))
        if missing:
            raise RuntimeError(
                "Restore target has no compatible Trading schema: " + ", ".join(missing)
            )
        check_schema(engine)
        with engine.connect() as connection:
            if connection.execute(text("SELECT current_database()" )).scalar_one() in {
                "postgres",
                "template0",
                "template1",
            }:
                raise RuntimeError("Refusing to restore into a PostgreSQL system database")
            nonempty = []
            for table in inventory["tables"]:
                count = int(
                    connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
                    or 0
                )
                if count:
                    nonempty.append(f"{table}={count}")
            if nonempty:
                raise RuntimeError(
                    "Restore target Trading tables must be empty: " + ", ".join(nonempty)
                )
    finally:
        engine.dispose()
    restore_env = _database_env(database_url)
    _run(
        [
            _tool("pg_restore"),
            "--no-owner",
            "--no-acl",
            "--data-only",
            "--exit-on-error",
            "--dbname",
            restore_env["PGDATABASE"],
            str(archive),
        ],
        env=restore_env,
    )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Trading external-schema backup utility")
    parser.add_argument("command", choices=("backup", "validate", "restore"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--confirm-isolated-target", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        result = archive_inventory(args.path)
    else:
        if not args.database_url:
            raise RuntimeError("DATABASE_URL is required")
        if args.command == "backup":
            result = create_backup(database_url=args.database_url, output=args.path)
        else:
            result = restore_backup(
                database_url=args.database_url,
                archive=args.path,
                confirm_isolated_target=args.confirm_isolated_target,
            )
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

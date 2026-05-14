from __future__ import annotations

import json
from db import pg_compat as dbcompat
from datetime import datetime
from pathlib import Path
from typing import Any

from services.ui_helpers import ROOT_DIR


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def ensure_catalog_pipeline_runs_table(conn: dbcompat.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            parameters_json TEXT,
            result_json TEXT,
            error_message TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_catalog_pipeline_runs_operation_started ON catalog_pipeline_runs(operation, started_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_catalog_pipeline_runs_status_started ON catalog_pipeline_runs(status, started_at DESC)")
    conn.commit()


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def start_run(operation: str, parameters: dict[str, Any] | None = None) -> int:
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_catalog_pipeline_runs_table(conn)
        cur = conn.execute(
            """
            INSERT INTO catalog_pipeline_runs (operation, status, started_at, parameters_json, result_json)
            VALUES (?, 'running', ?, ?, '{}')
            """,
            (operation, now_iso(), _json_dumps(parameters)),
        )
        conn.commit()
        return int(cur.lastrowid)


def finish_run(run_id: int, status: str, result: dict[str, Any] | None = None, error_message: str | None = None) -> None:
    finished_at = now_iso()
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_catalog_pipeline_runs_table(conn)
        row = conn.execute("SELECT started_at FROM catalog_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        duration = None
        if row and row[0]:
            try:
                started = datetime.fromisoformat(str(row[0]))
                finished = datetime.fromisoformat(finished_at)
                duration = round((finished - started).total_seconds(), 3)
            except Exception:
                duration = None
        conn.execute(
            """
            UPDATE catalog_pipeline_runs
               SET status=?, finished_at=?, duration_seconds=?, result_json=?, error_message=?
             WHERE id=?
            """,
            (status, finished_at, duration, _json_dumps(result), error_message, run_id),
        )
        conn.commit()


def get_recent_runs(limit: int = 20) -> list[dbcompat.Row]:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_catalog_pipeline_runs_table(conn)
        return list(conn.execute(
            """
            SELECT id, operation, status, started_at, finished_at, duration_seconds,
                   parameters_json, result_json, error_message
              FROM catalog_pipeline_runs
             ORDER BY started_at DESC, id DESC
             LIMIT ?
            """,
            (int(limit),),
        ).fetchall())


def get_last_run(operation: str | None = None) -> dbcompat.Row | None:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_catalog_pipeline_runs_table(conn)
        if operation:
            return conn.execute(
                """
                SELECT * FROM catalog_pipeline_runs
                 WHERE operation=?
                 ORDER BY started_at DESC, id DESC
                 LIMIT 1
                """,
                (operation,),
            ).fetchone()
        return conn.execute(
            """
            SELECT * FROM catalog_pipeline_runs
             ORDER BY started_at DESC, id DESC
             LIMIT 1
            """,
        ).fetchone()


def bootstrap() -> None:
    ROOT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_catalog_pipeline_runs_table(conn)

from __future__ import annotations

import json
from db import pg_compat as dbcompat
from datetime import datetime
from typing import Any

from services.ui_helpers import ROOT_DIR


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _table_columns(conn: dbcompat.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def ensure_market_data_pipeline_runs_table(conn: dbcompat.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_data_pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_run_id INTEGER,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            parameters_json TEXT,
            result_summary_json TEXT,
            stdout_tail TEXT,
            stderr_tail TEXT,
            error_message TEXT
        )
        """
    )
    columns = _table_columns(conn, "market_data_pipeline_runs")
    if "parent_run_id" not in columns:
        conn.execute("ALTER TABLE market_data_pipeline_runs ADD COLUMN parent_run_id INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_data_pipeline_runs_parent_started "
        "ON market_data_pipeline_runs(parent_run_id, started_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_data_pipeline_runs_operation_started "
        "ON market_data_pipeline_runs(operation, started_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_data_pipeline_runs_status_started "
        "ON market_data_pipeline_runs(status, started_at DESC)"
    )
    conn.commit()


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def start_run(operation: str, parameters: dict[str, Any] | None = None, parent_run_id: int | None = None) -> int:
    ROOT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_market_data_pipeline_runs_table(conn)
        cur = conn.execute(
            """
            INSERT INTO market_data_pipeline_runs (
                parent_run_id, operation, status, started_at, parameters_json,
                result_summary_json, stdout_tail, stderr_tail, error_message
            ) VALUES (?, ?, 'running', ?, ?, '{}', '', '', NULL)
            """,
            (parent_run_id, operation, now_iso(), _json_dumps(parameters)),
        )
        conn.commit()
        return int(cur.lastrowid)


def _tail_lines(text: str, limit: int = 50) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-limit:])


def finish_run(
    run_id: int,
    status: str,
    result_summary: dict[str, Any] | None = None,
    stdout_tail: str = "",
    stderr_tail: str = "",
    error_message: str | None = None,
) -> None:
    finished_at = now_iso()
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_market_data_pipeline_runs_table(conn)
        row = conn.execute("SELECT started_at FROM market_data_pipeline_runs WHERE id=?", (run_id,)).fetchone()
        duration = None
        if row and row[0]:
            try:
                duration = round((datetime.fromisoformat(finished_at) - datetime.fromisoformat(str(row[0]))).total_seconds(), 3)
            except Exception:
                duration = None
        conn.execute(
            """
            UPDATE market_data_pipeline_runs
               SET status=?, finished_at=?, duration_seconds=?, result_summary_json=?,
                   stdout_tail=?, stderr_tail=?, error_message=?
             WHERE id=?
            """,
            (
                status,
                finished_at,
                duration,
                _json_dumps(result_summary),
                _tail_lines(stdout_tail, 50),
                _tail_lines(stderr_tail, 50),
                error_message,
                run_id,
            ),
        )
        conn.commit()


def record_run(
    operation: str,
    status: str,
    parameters: dict[str, Any] | None,
    result_summary: dict[str, Any] | None,
    stdout_tail: str = "",
    stderr_tail: str = "",
    error_message: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_seconds: float | None = None,
    parent_run_id: int | None = None,
) -> int:
    ROOT_DIR.parent.mkdir(parents=True, exist_ok=True)
    started = started_at or now_iso()
    finished = finished_at or now_iso()
    if duration_seconds is None:
        try:
            duration_seconds = round((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds(), 3)
        except Exception:
            duration_seconds = None
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_market_data_pipeline_runs_table(conn)
        cur = conn.execute(
            """
            INSERT INTO market_data_pipeline_runs (
                parent_run_id, operation, status, started_at, finished_at, duration_seconds,
                parameters_json, result_summary_json, stdout_tail, stderr_tail, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parent_run_id,
                operation,
                status,
                started,
                finished,
                duration_seconds,
                _json_dumps(parameters),
                _json_dumps(result_summary),
                _tail_lines(stdout_tail, 50),
                _tail_lines(stderr_tail, 50),
                error_message,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_recent_runs(limit: int = 20, main_only: bool = False) -> list[dbcompat.Row]:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_market_data_pipeline_runs_table(conn)
        where = "WHERE parent_run_id IS NULL" if main_only else ""
        return list(
            conn.execute(
                f"""
                SELECT id, parent_run_id, operation, status, started_at, finished_at, duration_seconds,
                       parameters_json, result_summary_json, stdout_tail, stderr_tail, error_message
                  FROM market_data_pipeline_runs
                  {where}
                 ORDER BY started_at DESC, id DESC
                 LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        )


def get_child_runs(parent_run_id: int) -> list[dbcompat.Row]:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_market_data_pipeline_runs_table(conn)
        return list(
            conn.execute(
                """
                SELECT id, parent_run_id, operation, status, started_at, finished_at, duration_seconds,
                       parameters_json, result_summary_json, stdout_tail, stderr_tail, error_message
                  FROM market_data_pipeline_runs
                 WHERE parent_run_id=?
                 ORDER BY id ASC
                """,
                (int(parent_run_id),),
            ).fetchall()
        )


def get_last_run(operation: str | None = None) -> dbcompat.Row | None:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_market_data_pipeline_runs_table(conn)
        if operation:
            return conn.execute(
                """
                SELECT * FROM market_data_pipeline_runs
                 WHERE operation=?
                 ORDER BY started_at DESC, id DESC
                 LIMIT 1
                """,
                (operation,),
            ).fetchone()
        return conn.execute(
            """
            SELECT * FROM market_data_pipeline_runs
             ORDER BY started_at DESC, id DESC
             LIMIT 1
            """
        ).fetchone()


def bootstrap() -> None:
    ROOT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with dbcompat.connect(ROOT_DIR) as conn:
        ensure_market_data_pipeline_runs_table(conn)

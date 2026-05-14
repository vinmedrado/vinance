
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import json

from sqlalchemy import text

from services.db_session import db_session

MAX_CONCURRENT_JOBS = 2
MAX_QUEUE_SIZE = 20


def _dump(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _load(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def ensure_background_jobs_table() -> None:
    with db_session() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS background_jobs (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                parameters_json TEXT,
                result_json TEXT,
                error_message TEXT,
                stdout_tail TEXT,
                stderr_tail TEXT,
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 0,
                progress_label TEXT,
                priority INTEGER DEFAULT 0,
                effective_priority INTEGER DEFAULT 0,
                queue_reason TEXT,
                last_queue_check_at TEXT,
                is_stale_running BOOLEAN DEFAULT FALSE
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON background_jobs(status, effective_priority DESC, priority DESC, created_at ASC)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON background_jobs(job_type, status)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON background_jobs(tenant_id)"))
        db.commit()


def create_job(job_type: str, parameters: dict[str, Any], priority: int = 0, tenant_id: str | None = None) -> int:
    ensure_background_jobs_table()
    with db_session() as db:
        queued = db.execute(text("SELECT COUNT(*) AS total FROM background_jobs WHERE status='queued'")).mappings().first()
        if int(queued["total"] or 0) > MAX_QUEUE_SIZE:
            raise RuntimeError("Muitos jobs na fila. Aguarde ou limpe a fila.")

        duplicate = db.execute(
            text("""
                SELECT id FROM background_jobs
                WHERE job_type=:job_type
                  AND status IN ('queued','running')
                  AND parameters_json=:parameters_json
                  AND (:tenant_id IS NULL OR tenant_id=:tenant_id)
                LIMIT 1
            """),
            {"job_type": job_type, "parameters_json": _dump(parameters), "tenant_id": tenant_id},
        ).mappings().first()
        if duplicate:
            raise RuntimeError("Já existe um job semelhante em execução ou na fila.")

        row = db.execute(
            text("""
                INSERT INTO background_jobs
                (tenant_id, job_type, status, created_at, parameters_json, result_json, priority, effective_priority, queue_reason)
                VALUES (:tenant_id, :job_type, 'queued', :created_at, :parameters_json, '{}', :priority, :priority, 'aguardando execução')
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "job_type": job_type,
                "created_at": datetime.utcnow().isoformat(),
                "parameters_json": _dump(parameters),
                "priority": int(priority),
            },
        ).mappings().first()
        db.commit()
        return int(row["id"])


def start_job(job_id: int) -> None:
    ensure_background_jobs_table()
    with db_session() as db:
        db.execute(
            text("""
                UPDATE background_jobs
                SET status='running', started_at=:started_at, queue_reason=NULL
                WHERE id=:id AND status='queued'
            """),
            {"id": int(job_id), "started_at": datetime.utcnow().isoformat()},
        )
        db.commit()


def update_job_progress(job_id: int, current: int, total: int, label: str) -> None:
    with db_session() as db:
        db.execute(
            text("""
                UPDATE background_jobs
                SET progress_current=:current, progress_total=:total, progress_label=:label
                WHERE id=:id
            """),
            {"id": int(job_id), "current": int(current), "total": int(total), "label": label},
        )
        db.commit()


def finish_job(job_id: int, result: dict[str, Any], stdout_tail: str | None = None, stderr_tail: str | None = None, status: str = "success") -> None:
    finished = datetime.utcnow().isoformat()
    with db_session() as db:
        row = db.execute(text("SELECT started_at FROM background_jobs WHERE id=:id"), {"id": int(job_id)}).mappings().first()
        duration = None
        if row and row["started_at"]:
            try:
                duration = (datetime.fromisoformat(finished) - datetime.fromisoformat(row["started_at"])).total_seconds()
            except Exception:
                pass
        db.execute(
            text("""
                UPDATE background_jobs
                SET status=:status, finished_at=:finished_at, duration_seconds=:duration,
                    result_json=:result_json, stdout_tail=:stdout_tail, stderr_tail=:stderr_tail
                WHERE id=:id
            """),
            {
                "id": int(job_id),
                "status": status,
                "finished_at": finished,
                "duration": duration,
                "result_json": _dump(result),
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            },
        )
        db.commit()


def fail_job(job_id: int, error: str, stdout_tail: str | None = None, stderr_tail: str | None = None) -> None:
    finish_job(job_id, {"error": error}, stdout_tail, stderr_tail, status="failed")
    with db_session() as db:
        db.execute(text("UPDATE background_jobs SET error_message=:error WHERE id=:id"), {"id": int(job_id), "error": error})
        db.commit()


def cancel_job(job_id: int) -> None:
    with db_session() as db:
        db.execute(
            text("""
                UPDATE background_jobs
                SET status='canceled', queue_reason='cancelado', finished_at=:finished_at
                WHERE id=:id AND status IN ('queued','running')
            """),
            {"id": int(job_id), "finished_at": datetime.utcnow().isoformat()},
        )
        db.commit()


def cancel_queued_jobs(tenant_id: str | None = None) -> int:
    with db_session() as db:
        result = db.execute(
            text("""
                UPDATE background_jobs
                SET status='canceled', queue_reason='cancelado', finished_at=:finished_at
                WHERE status='queued' AND (:tenant_id IS NULL OR tenant_id=:tenant_id)
            """),
            {"tenant_id": tenant_id, "finished_at": datetime.utcnow().isoformat()},
        )
        db.commit()
        return int(result.rowcount or 0)


def get_job(job_id: int) -> dict[str, Any] | None:
    ensure_background_jobs_table()
    with db_session() as db:
        row = db.execute(text("SELECT * FROM background_jobs WHERE id=:id"), {"id": int(job_id)}).mappings().first()
        if not row:
            return None
        out = dict(row)
        out["parameters"] = _load(out.get("parameters_json"))
        out["result"] = _load(out.get("result_json"))
        return out


def list_jobs(limit: int = 50, status: str | None = None, job_type: str | None = None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    ensure_background_jobs_table()
    where = []
    params: dict[str, Any] = {"limit": int(limit)}
    if status:
        where.append("status=:status")
        params["status"] = status
    if job_type:
        where.append("job_type=:job_type")
        params["job_type"] = job_type
    if tenant_id:
        where.append("tenant_id=:tenant_id")
        params["tenant_id"] = tenant_id
    sql = "SELECT * FROM background_jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT :limit"
    with db_session() as db:
        rows = db.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


def get_next_queued_job() -> dict[str, Any] | None:
    ensure_background_jobs_table()
    with db_session() as db:
        row = db.execute(
            text("""
                SELECT *
                FROM background_jobs
                WHERE status='queued'
                ORDER BY effective_priority DESC, priority DESC, created_at ASC
                LIMIT 1
            """)
        ).mappings().first()
        return dict(row) if row else None


def count_running_jobs(job_type: str | None = None) -> int:
    sql = "SELECT COUNT(*) AS total FROM background_jobs WHERE status='running'"
    params = {}
    if job_type:
        sql += " AND job_type=:job_type"
        params["job_type"] = job_type
    with db_session() as db:
        row = db.execute(text(sql), params).mappings().first()
        return int(row["total"] or 0)


def cleanup_old_jobs(days: int = 30) -> int:
    cutoff = (datetime.utcnow() - timedelta(days=int(days))).isoformat()
    with db_session() as db:
        result = db.execute(
            text("""
                DELETE FROM background_jobs
                WHERE status IN ('success','failed','canceled')
                  AND created_at < :cutoff
            """),
            {"cutoff": cutoff},
        )
        db.commit()
        return int(result.rowcount or 0)


def mark_stale_running(hours: int = 2) -> int:
    cutoff = (datetime.utcnow() - timedelta(hours=int(hours))).isoformat()
    with db_session() as db:
        result = db.execute(
            text("""
                UPDATE background_jobs
                SET is_stale_running=true
                WHERE status='running' AND started_at < :cutoff
            """),
            {"cutoff": cutoff},
        )
        db.commit()
        return int(result.rowcount or 0)


def queue_summary() -> dict[str, int]:
    ensure_background_jobs_table()
    with db_session() as db:
        rows = db.execute(
            text("""
                SELECT status, COUNT(*) AS total
                FROM background_jobs
                GROUP BY status
            """)
        ).mappings().all()
        data = {r["status"]: int(r["total"]) for r in rows}
        return {
            "running": data.get("running", 0),
            "queued": data.get("queued", 0),
            "success": data.get("success", 0),
            "failed": data.get("failed", 0),
            "canceled": data.get("canceled", 0),
            "max_concurrent": MAX_CONCURRENT_JOBS,
        }

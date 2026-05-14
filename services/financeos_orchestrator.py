
from __future__ import annotations

import json
from db import pg_compat as dbcompat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from services.background_jobs import fail_job, finish_job, finish_partial_success_job, get_job, update_job_progress
from services.agents.agent_manager import run_all_agents

ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR = ROOT / "data" / "POSTGRES_RUNTIME_DISABLED"
SCRIPTS_DIR = ROOT / "scripts"
TIMEOUT_SECONDS = 60 * 60

VALID_MODES = {"rapido", "completo", "pesquisa"}
VALID_ASSET_CLASSES = {"all", "equity", "fii", "etf", "bdr", "crypto", "currency", "commodity", "index", "unknown"}

RETRYABLE_ERROR_TYPES = {"api_error", "timeout"}
NON_RETRYABLE_ERROR_TYPES = {"schema_error", "script_missing", "invalid_args"}
EMPTY_STDOUT_WARNING_STEPS = {
    "validate_catalog",
    "update_quality_scores",
    "sync_assets",
    "sync_crypto_catalog",
    "sync_prices",
    "sync_dividends",
    "sync_indices",
    "sync_macro",
    "coverage_report",
    "analysis_engine",
    "analysis_report",
    "backtest",
    "backtest_report",
}

ALLOWED_SCRIPTS = {
    "sync_crypto_catalog.py",
    "validate_asset_catalog.py",
    "update_asset_quality_scores.py",
    "sync_assets_from_catalog.py",
    "sync_historical_prices.py",
    "sync_dividends.py",
    "sync_market_indices.py",
    "sync_macro_indicators.py",
    "report_data_coverage.py",
    "run_analysis_engine.py",
    "report_analysis_summary.py",
    "run_strategy_backtest.py",
    "report_backtest.py",
}

STEP_DEFINITIONS = {
    "validate_catalog": {"script": "validate_asset_catalog.py", "critical": True},
    "update_quality_scores": {"script": "update_asset_quality_scores.py", "critical": False},
    "sync_assets": {"script": "sync_assets_from_catalog.py", "critical": True},
    "sync_crypto_catalog": {"script": "sync_crypto_catalog.py", "critical": False},
    "sync_prices": {"script": "sync_historical_prices.py", "critical": False},
    "sync_dividends": {"script": "sync_dividends.py", "critical": False},
    "sync_indices": {"script": "sync_market_indices.py", "critical": False},
    "sync_macro": {"script": "sync_macro_indicators.py", "critical": False},
    "coverage_report": {"script": "report_data_coverage.py", "critical": False},
    "analysis_engine": {"script": "run_analysis_engine.py", "critical": False},
    "analysis_report": {"script": "report_analysis_summary.py", "critical": False},
    "backtest": {"script": "run_strategy_backtest.py", "critical": False},
    "backtest_report": {"script": "report_backtest.py", "critical": False},
}

MODE_STEPS = {
    "rapido": [
        "validate_catalog",
        "update_quality_scores",
        "sync_assets",
        "sync_prices",
        "coverage_report",
    ],
    "completo": [
        "validate_catalog",
        "update_quality_scores",
        "sync_assets",
        "sync_crypto_catalog",
        "sync_prices",
        "sync_dividends",
        "sync_indices",
        "sync_macro",
        "coverage_report",
        "analysis_engine",
        "analysis_report",
    ],
    "pesquisa": [
        "validate_catalog",
        "update_quality_scores",
        "sync_assets",
        "sync_crypto_catalog",
        "sync_prices",
        "sync_dividends",
        "sync_indices",
        "sync_macro",
        "coverage_report",
        "analysis_engine",
        "analysis_report",
        "backtest",
        "backtest_report",
    ],
}


def _now() -> str:
    return datetime.utcnow().isoformat()


def _connect() -> dbcompat.Connection:
    ROOT_DIR.parent.mkdir(parents=True, exist_ok=True)
    conn = dbcompat.connect(ROOT_DIR, timeout=30, check_same_thread=False)
    conn.row_factory = dbcompat.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _json_dump(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def _json_load(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return raw or {}


def tail_lines(text: str | None, limit: int = 50) -> str:
    return "\n".join((text or "").splitlines()[-limit:])


def bootstrap() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrator_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                mode TEXT,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                parameters_json TEXT,
                result_json TEXT,
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orchestrator_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orchestrator_run_id INTEGER,
                step_name TEXT,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                summary_json TEXT,
                stdout_tail TEXT,
                stderr_tail TEXT,
                error_message TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_started ON orchestrator_runs (started_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_job ON orchestrator_runs (job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_orchestrator_steps_run ON orchestrator_steps (orchestrator_run_id)")


def _duration(start: str, end: str) -> float:
    try:
        return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3)
    except Exception:
        return 0.0


def start_orchestrator_run(job_id: int | None, mode: str, params: dict[str, Any]) -> int:
    started = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO orchestrator_runs (
                job_id, mode, status, started_at, parameters_json, result_json
            ) VALUES (?, ?, 'running', ?, ?, '{}')
            """,
            (job_id, mode, started, _json_dump(params)),
        )
        return int(cur.lastrowid)


def finish_orchestrator_run(run_id: int, status: str, result: dict[str, Any], error: str | None = None) -> None:
    finished = _now()
    with _connect() as conn:
        row = conn.execute("SELECT started_at FROM orchestrator_runs WHERE id=?", (int(run_id),)).fetchone()
        duration = _duration(row["started_at"], finished) if row else 0
        conn.execute(
            """
            UPDATE orchestrator_runs
            SET status=?, finished_at=?, duration_seconds=?, result_json=?, error_message=?
            WHERE id=?
            """,
            (status, finished, duration, _json_dump(result), error, int(run_id)),
        )


def start_step(run_id: int, step_name: str) -> int:
    started = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO orchestrator_steps (
                orchestrator_run_id, step_name, status, started_at, summary_json
            ) VALUES (?, ?, 'running', ?, '{}')
            """,
            (int(run_id), step_name, started),
        )
        return int(cur.lastrowid)


def finish_step(step_id: int, status: str, summary: dict[str, Any], stdout_tail: str = "", stderr_tail: str = "", error: str | None = None) -> None:
    finished = _now()
    with _connect() as conn:
        row = conn.execute("SELECT started_at FROM orchestrator_steps WHERE id=?", (int(step_id),)).fetchone()
        duration = _duration(row["started_at"], finished) if row else 0
        conn.execute(
            """
            UPDATE orchestrator_steps
            SET status=?, finished_at=?, duration_seconds=?, summary_json=?, stdout_tail=?, stderr_tail=?, error_message=?
            WHERE id=?
            """,
            (status, finished, duration, _json_dump(summary), tail_lines(stdout_tail), tail_lines(stderr_tail), error, int(step_id)),
        )


def get_recent_orchestrator_runs(limit: int = 20) -> list[dbcompat.Row]:
    bootstrap()
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM orchestrator_runs ORDER BY started_at DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()


def get_orchestrator_run(run_id: int) -> dbcompat.Row | None:
    bootstrap()
    with _connect() as conn:
        return conn.execute("SELECT * FROM orchestrator_runs WHERE id=?", (int(run_id),)).fetchone()


def get_orchestrator_steps(run_id: int) -> list[dbcompat.Row]:
    bootstrap()
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM orchestrator_steps WHERE orchestrator_run_id=? ORDER BY id ASC",
            (int(run_id),),
        ).fetchall()


def validate_params(params: dict[str, Any]) -> dict[str, Any]:
    mode = str(params.get("mode") or "rapido").lower()
    aliases = {"rápido": "rapido", "rapido": "rapido", "completo": "completo", "pesquisa": "pesquisa"}
    mode = aliases.get(mode, mode)
    if mode not in VALID_MODES:
        raise ValueError("Modo inválido. Use rápido, completo ou pesquisa.")

    asset_class = str(params.get("asset_class") or "all").lower()
    if asset_class not in VALID_ASSET_CLASSES:
        raise ValueError("asset_class inválido.")

    limit_raw = params.get("limit", 200)
    limit = None if limit_raw in (None, "", 0) else int(limit_raw)
    if limit is not None and limit < 0:
        raise ValueError("limit deve ser maior ou igual a 0.")

    max_age_days = int(params.get("max_age_days", 7) or 7)
    if max_age_days < 0:
        raise ValueError("max_age_days deve ser maior ou igual a 0.")

    top_n = int(params.get("top_n", 50) or 50)
    if top_n < 0:
        raise ValueError("top_n deve ser maior ou igual a 0.")

    initial_capital = float(params.get("initial_capital", 10000) or 10000)
    if initial_capital <= 0:
        raise ValueError("initial_capital deve ser maior que 0.")

    clean = {
        "mode": mode,
        "asset_class": asset_class,
        "limit": limit,
        "max_age_days": max_age_days,
        "force": bool(params.get("force", False)),
        "dry_run": bool(params.get("dry_run", False)),
        "incremental": bool(params.get("incremental", True)),
        "run_backtest": bool(params.get("run_backtest", False)),
        "retry_non_critical_steps": bool(params.get("retry_non_critical_steps", True)),
        "top_n": top_n,
        "start_date": str(params.get("start_date") or "").strip(),
        "end_date": str(params.get("end_date") or "").strip(),
        "initial_capital": initial_capital,
    }
    return clean


def _append_arg(args: list[str], flag: str, value: Any, skip_values: tuple[Any, ...] = ("", None, "all")) -> None:
    if value in skip_values:
        return
    args.extend([flag, str(value)])


def build_step_args(step_name: str, params: dict[str, Any]) -> list[str]:
    args: list[str] = []
    limit = params.get("limit")
    asset_class = params.get("asset_class")

    if step_name in {"validate_catalog", "update_quality_scores", "sync_assets", "sync_crypto_catalog"}:
        _append_arg(args, "--limit", limit)
        _append_arg(args, "--asset-class", asset_class)
        if step_name == "validate_catalog":
            _append_arg(args, "--max-age-days", params.get("max_age_days"))
            if params.get("force"):
                args.append("--force")
        if params.get("dry_run") and step_name != "validate_catalog":
            args.append("--dry-run")

    elif step_name in {"sync_prices", "sync_dividends"}:
        _append_arg(args, "--limit", limit)
        _append_arg(args, "--asset-class", asset_class)
        if step_name == "sync_prices" and params.get("incremental"):
            args.append("--incremental")
        if params.get("dry_run"):
            args.append("--dry-run")

    elif step_name == "sync_indices":
        _append_arg(args, "--limit", limit)
        if params.get("dry_run"):
            args.append("--dry-run")

    elif step_name == "sync_macro":
        if params.get("dry_run"):
            args.append("--dry-run")

    elif step_name in {"analysis_engine", "analysis_report"}:
        _append_arg(args, "--limit", limit)
        _append_arg(args, "--top-n", params.get("top_n"))

    elif step_name in {"backtest", "backtest_report"}:
        _append_arg(args, "--start-date", params.get("start_date"))
        _append_arg(args, "--end-date", params.get("end_date"))
        _append_arg(args, "--initial-capital", params.get("initial_capital"))
        _append_arg(args, "--top-n", params.get("top_n"))

    return args


def safe_command(script_name: str, args: list[str]) -> list[str]:
    if script_name not in ALLOWED_SCRIPTS:
        raise ValueError(f"Script não permitido: {script_name}")
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        raise FileNotFoundError(f"Script não encontrado: {script}")
    return [sys.executable, str(script), *args]


def classify_step_error(stderr: str | None, stdout: str | None) -> str:
    text = f"{stderr or ''}\n{stdout or ''}".lower()

    if "no such file" in text or "script não encontrado" in text or "filenotfounderror" in text:
        return "script_missing"
    if "unrecognized arguments" in text or "invalid choice" in text or "argumenterror" in text or "usage:" in text:
        return "invalid_args"
    if "no such table" in text or "no such column" in text or "database schema" in text or "schema" in text:
        return "schema_error"
    if "timeout" in text or "timed out" in text or "read timed out" in text:
        return "timeout"
    if "429" in text or "rate limit" in text or "too many requests" in text or "connection" in text or "api" in text or "http" in text:
        return "api_error"
    return "unknown"


def _return_validation(step_name: str, returncode: int, stdout: str, stderr: str, duration: float) -> dict[str, Any]:
    error_type = classify_step_error(stderr, stdout)
    stdout_clean = (stdout or "").strip()
    stderr_clean = (stderr or "").strip()

    summary = {
        "returncode": int(returncode),
        "duration_seconds": round(duration, 3),
        "stdout_tail": tail_lines(stdout, 15),
        "stderr_tail": tail_lines(stderr, 15),
        "error_type": error_type,
        "warning_message": None,
    }

    if returncode != 0:
        return {
            "status": "failed",
            "summary": summary,
            "error_message": f"Script retornou código {returncode}. Tipo: {error_type}.",
        }

    if step_name in EMPTY_STDOUT_WARNING_STEPS and not stdout_clean:
        summary["warning_message"] = "Script executou, mas não retornou saída relevante."
        return {
            "status": "warning",
            "summary": summary,
            "error_message": None,
        }

    return {
        "status": "success",
        "summary": summary,
        "error_message": None,
    }


def _execute_process(script: str, args: list[str]) -> tuple[int, str, str, float]:
    cmd = safe_command(script, args)
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        shell=False,
    )
    duration = time.perf_counter() - started
    return int(proc.returncode), proc.stdout or "", proc.stderr or "", duration


def run_step_script_once(step_name: str, params: dict[str, Any]) -> dict[str, Any]:
    definition = STEP_DEFINITIONS[step_name]
    script = definition["script"]
    args = build_step_args(step_name, params)
    try:
        returncode, stdout, stderr, duration = _execute_process(script, args)
        validation = _return_validation(step_name, returncode, stdout, stderr, duration)
        return {
            "step_name": step_name,
            "script": script,
            "args": args,
            "status": validation["status"],
            "summary": validation["summary"],
            "stdout_tail": tail_lines(stdout),
            "stderr_tail": tail_lines(stderr),
            "error_message": validation["error_message"],
            "duration_seconds": round(duration, 3),
        }
    except FileNotFoundError as exc:
        return {
            "step_name": step_name,
            "script": script,
            "args": args,
            "status": "failed",
            "summary": {"status_final": "failed", "error_type": "script_missing", "duration_seconds": 0},
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "error_message": f"Script ausente: {exc}",
            "duration_seconds": 0,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else str(exc)
        return {
            "step_name": step_name,
            "script": script,
            "args": args,
            "status": "failed",
            "summary": {"status_final": "failed", "error_type": "timeout", "duration_seconds": TIMEOUT_SECONDS},
            "stdout_tail": tail_lines(stdout),
            "stderr_tail": tail_lines(stderr),
            "error_message": "Timeout na execução da etapa.",
            "duration_seconds": TIMEOUT_SECONDS,
        }
    except ValueError as exc:
        return {
            "step_name": step_name,
            "script": script,
            "args": args,
            "status": "failed",
            "summary": {"status_final": "failed", "error_type": "invalid_args", "duration_seconds": 0},
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "error_message": str(exc),
            "duration_seconds": 0,
        }
    except Exception as exc:
        return {
            "step_name": step_name,
            "script": script,
            "args": args,
            "status": "failed",
            "summary": {"status_final": "failed", "error_type": classify_step_error(str(exc), ""), "duration_seconds": 0},
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "error_message": str(exc),
            "duration_seconds": 0,
        }


def should_retry_step(step_name: str, result: dict[str, Any], params: dict[str, Any]) -> bool:
    if not params.get("retry_non_critical_steps", True):
        return False
    if STEP_DEFINITIONS[step_name].get("critical"):
        return False
    if result.get("status") != "failed":
        return False
    error_type = ((result.get("summary") or {}).get("error_type")) or classify_step_error(result.get("stderr_tail"), result.get("stdout_tail"))
    return error_type in RETRYABLE_ERROR_TYPES and error_type not in NON_RETRYABLE_ERROR_TYPES


def run_step_script(step_name: str, params: dict[str, Any]) -> dict[str, Any]:
    first = run_step_script_once(step_name, params)
    first_summary = dict(first.get("summary") or {})
    first_summary["retries_attempted"] = 0
    first_summary["retry_success"] = False
    first["summary"] = first_summary

    if not should_retry_step(step_name, first, params):
        return first

    retry = run_step_script_once(step_name, params)
    retry_summary = dict(retry.get("summary") or {})
    retry_summary["retries_attempted"] = 1
    retry_summary["retry_success"] = retry.get("status") in {"success", "warning"}
    retry_summary["first_attempt_status"] = first.get("status")
    retry_summary["first_attempt_error"] = first.get("error_message")
    retry["summary"] = retry_summary
    if retry.get("status") in {"success", "warning"}:
        retry["stdout_tail"] = f"### Tentativa 1 falhou\n{first.get('stdout_tail', '')}\n\n### Retry OK\n{retry.get('stdout_tail', '')}"
        retry["stderr_tail"] = f"### Tentativa 1 falhou\n{first.get('stderr_tail', '')}\n\n### Retry\n{retry.get('stderr_tail', '')}"
    return retry


def _steps_for_mode(params: dict[str, Any]) -> list[str]:
    mode = params["mode"]
    steps = list(MODE_STEPS[mode])
    if params.get("run_backtest") and "backtest" not in steps:
        steps.extend(["backtest", "backtest_report"])
    return steps


def _is_job_canceled(job_id: int | None) -> bool:
    if not job_id:
        return False
    row = get_job(int(job_id))
    return bool(row and row["status"] == "canceled")


def _final_message(status: str, total: int, success: int, failed: int, warnings: int, skipped: int) -> str:
    if status == "success":
        return f"Execução concluída com sucesso. {success} de {total} etapas concluídas."
    if status == "warning":
        return f"Execução concluída com alertas. {success} etapas concluídas, {warnings} com alerta e {failed} com erro."
    if status == "partial_success":
        return f"Execução concluída parcialmente. {success} etapas concluídas, {failed} com erro e {warnings} com alerta."
    if skipped:
        return f"Execução interrompida. {skipped} etapa(s) não executada(s)."
    return f"Execução falhou. {failed} etapa(s) com erro."


def _build_executive_summary(params: dict[str, Any], results: list[dict[str, Any]], planned_steps: list[str], started: float, critical_failure: bool, skipped_steps: int) -> dict[str, Any]:
    success_steps = sum(1 for r in results if r.get("status") == "success")
    warning_steps = sum(1 for r in results if r.get("status") == "warning")
    failed_steps = sum(1 for r in results if r.get("status") == "failed")
    critical_failures = sum(1 for r in results if r.get("status") == "failed" and STEP_DEFINITIONS.get(r.get("step_name"), {}).get("critical"))
    non_critical_failures = max(failed_steps - critical_failures, 0)

    if critical_failure:
        status = "failed"
    elif failed_steps > 0:
        status = "partial_success"
    elif warning_steps > 0:
        status = "warning"
    else:
        status = "success"

    return {
        "mode": params.get("mode"),
        "status": status,
        "status_final": status,
        "execution_outcome": status,
        "has_warnings": bool(status in {"partial_success", "warning"} or warning_steps > 0),
        "total_steps": len(planned_steps),
        "success_steps": success_steps,
        "failed_steps": failed_steps,
        "warning_steps": warning_steps,
        "skipped_steps": int(skipped_steps),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "critical_failures": critical_failures,
        "non_critical_failures": non_critical_failures,
        "final_message": _final_message(status, len(planned_steps), success_steps, failed_steps, warning_steps, skipped_steps),
        "steps": [
            {
                "step_name": r.get("step_name"),
                "status": r.get("status"),
                "duration_seconds": r.get("duration_seconds"),
                "error_type": (r.get("summary") or {}).get("error_type"),
                "retries_attempted": (r.get("summary") or {}).get("retries_attempted", 0),
                "retry_success": (r.get("summary") or {}).get("retry_success", False),
                "error_message": r.get("error_message"),
            }
            for r in results
        ],
    }


def run_orchestrator(params: dict[str, Any], job_id: int | None = None) -> dict[str, Any]:
    """
    Executa ciclo operacional do FinanceOS via subprocess seguro.

    Best effort:
    - Falhas não críticas são registradas e o fluxo continua.
    - Falhas críticas interrompem o orquestrador.
    """
    bootstrap()
    clean_params = validate_params(params)
    planned_steps = _steps_for_mode(clean_params)
    run_id = start_orchestrator_run(job_id, clean_params["mode"], clean_params)
    started = time.perf_counter()

    results: list[dict[str, Any]] = []
    critical_failure = False
    all_stdout: list[str] = []
    all_stderr: list[str] = []

    try:
        for idx, step_name in enumerate(planned_steps, start=1):
            if _is_job_canceled(job_id):
                results.append({"step_name": step_name, "status": "skipped", "error_message": "Cancelamento lógico solicitado."})
                break

            label = f"{idx}/{len(planned_steps)} · {step_name}"
            if job_id:
                update_job_progress(job_id, idx - 1, len(planned_steps), label)

            step_id = start_step(run_id, step_name)
            result = run_step_script(step_name, clean_params)
            finish_step(
                step_id,
                result["status"],
                {**result.get("summary", {}), "script": result.get("script"), "args": result.get("args")},
                result.get("stdout_tail", ""),
                result.get("stderr_tail", ""),
                result.get("error_message"),
            )
            results.append(result)
            all_stdout.append(f"### {step_name}\n{result.get('stdout_tail', '')}")
            if result.get("stderr_tail"):
                all_stderr.append(f"### {step_name}\n{result.get('stderr_tail', '')}")

            if result["status"] == "failed" and STEP_DEFINITIONS[step_name].get("critical"):
                critical_failure = True
                break

            if job_id:
                update_job_progress(job_id, idx, len(planned_steps), f"Etapa concluída: {step_name}")

        skipped_steps = max(len(planned_steps) - len(results), 0)
        summary = _build_executive_summary(clean_params, results, planned_steps, started, critical_failure, skipped_steps)
        try:
            agents_payload = run_all_agents({
                "orchestrator": summary,
                "orchestrator_run_id": run_id,
                "steps": summary.get("steps", []),
            })
            summary["agents"] = agents_payload
            summary["global_intelligence_score"] = agents_payload.get("global_intelligence_score")
            summary["top_insights"] = agents_payload.get("top_insights", [])
            summary["warnings"] = agents_payload.get("warnings", [])
            summary["opportunities"] = agents_payload.get("opportunities", [])
            summary["final_explanation"] = agents_payload.get("final_explanation")
            summary["intelligence_history"] = agents_payload.get("intelligence_history")
        except Exception as exc:
            summary["agents"] = {"error": str(exc), "mode": "fallback_failed"}
        finish_orchestrator_run(run_id, summary["status"], summary, "Falha crítica." if critical_failure else None)

        if job_id:
            if critical_failure or summary["status"] == "failed":
                fail_job(job_id, summary["final_message"], "\n\n".join(all_stdout), "\n\n".join(all_stderr))
            elif summary["status"] == "partial_success":
                finish_partial_success_job(job_id, summary, "\n\n".join(all_stdout), "\n\n".join(all_stderr))
            else:
                # success ou warning sem failed_steps continuam como job success,
                # mas o result_json preserva warning_steps/status.
                finish_job(job_id, summary, "\n\n".join(all_stdout), "\n\n".join(all_stderr))

        return summary

    except Exception as exc:
        results.append({"step_name": "orchestrator_runtime", "status": "failed", "error_message": str(exc)})
        summary = _build_executive_summary(clean_params, results, planned_steps, started, True, max(len(planned_steps) - len(results), 0))
        summary["final_message"] = f"Execução falhou por erro interno do orquestrador: {exc}"
        try:
            agents_payload = run_all_agents({
                "orchestrator": summary,
                "orchestrator_run_id": run_id,
                "steps": summary.get("steps", []),
            })
            summary["agents"] = agents_payload
            summary["global_intelligence_score"] = agents_payload.get("global_intelligence_score")
            summary["top_insights"] = agents_payload.get("top_insights", [])
            summary["warnings"] = agents_payload.get("warnings", [])
            summary["opportunities"] = agents_payload.get("opportunities", [])
            summary["final_explanation"] = agents_payload.get("final_explanation")
            summary["intelligence_history"] = agents_payload.get("intelligence_history")
        except Exception as agent_exc:
            summary["agents"] = {"error": str(agent_exc), "mode": "fallback_failed"}
        finish_orchestrator_run(run_id, "failed", summary, str(exc))
        if job_id:
            fail_job(job_id, str(exc), "\n\n".join(all_stdout), "\n\n".join(all_stderr))
        return summary


def run_orchestrator_job(job_id: int, params: dict[str, Any]) -> dict[str, Any]:
    return run_orchestrator(params, job_id=job_id)


bootstrap()

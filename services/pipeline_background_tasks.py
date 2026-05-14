from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from services.background_jobs import fail_job, finish_job, get_job, update_job_progress
from services.market_data_pipeline_runs import finish_run as finish_market_run
from services.market_data_pipeline_runs import start_run as start_market_run

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 60 * 45
VALID_MARKET_ASSET_CLASSES = {"all", "equity", "fii", "etf", "bdr", "crypto", "currency", "commodity", "index"}
VALID_CATALOG_ASSET_CLASSES = {"all", "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity", "unknown"}

MARKET_SCRIPT_MAP = {
    "historical_prices": "sync_historical_prices.py",
    "dividends": "sync_dividends.py",
    "market_indices": "sync_market_indices.py",
    "macro_indicators": "sync_macro_indicators.py",
    "data_coverage_report": "report_data_coverage.py",
    "prices_step": "sync_historical_prices.py",
    "dividends_step": "sync_dividends.py",
    "indices_step": "sync_market_indices.py",
    "macro_step": "sync_macro_indicators.py",
    "coverage_step": "report_data_coverage.py",
}

CATALOG_SCRIPT_MAP = {
    "validate_catalog": "validate_asset_catalog.py",
    "update_quality": "update_asset_quality_scores.py",
    "sync_assets": "sync_assets_from_catalog.py",
    "catalog_full_pipeline": "__pipeline__",
}


def tail_lines(text: str | None, limit: int = 50) -> str:
    return "\n".join((text or "").splitlines()[-limit:])


def clean_tickers(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    tickers: list[str] = []
    for token in re.split(r"[,;\s]+", str(raw).strip().upper()):
        if not token:
            continue
        if not re.fullmatch(r"[A-Z0-9_.\-]{2,20}", token):
            raise ValueError(f"Ticker inválido: {token}")
        tickers.append(token)
    return ",".join(dict.fromkeys(tickers)) if tickers else None


def safe_limit(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("limit deve ser maior ou igual a 0.")
    return parsed or None


def build_command(script_name: str, allowed: set[str]) -> list[str]:
    if script_name not in allowed:
        raise ValueError("Script não permitido para execução em background.")
    script = ROOT / "scripts" / script_name
    if not script.exists():
        raise FileNotFoundError(f"Script não encontrado: {script}")
    return [sys.executable, str(script)]


def parse_summary(stdout: str, stderr: str, returncode: int, duration: float) -> dict[str, Any]:
    output = f"{stdout or ''}\n{stderr or ''}"
    summary: dict[str, Any] = {
        "status_final": "SUCCESS" if returncode == 0 else "FAILED",
        "total_processado": None,
        "sucesso": None,
        "falhas": None,
        "ignorados": None,
        "inseridos": None,
        "atualizados": None,
        "tempo_execucao": round(duration, 3),
        "ultimas_linhas_log": tail_lines(output, 15),
    }
    patterns = {
        "total_processado": [r"processados\s*[:=]\s*(\d+)", r"total_processados['\"]?\s*[:=]\s*(\d+)", r"Total processado\s*[:=]\s*(\d+)"],
        "sucesso": [r"sucesso\s*[:=]\s*(\d+)", r"total_sucesso['\"]?\s*[:=]\s*(\d+)"],
        "falhas": [r"falhas\s*[:=]\s*(\d+)", r"total_falhas['\"]?\s*[:=]\s*(\d+)"],
        "ignorados": [r"ignorados\s*[:=]\s*(\d+)", r"total_ignorados['\"]?\s*[:=]\s*(\d+)"],
        "inseridos": [r"rows_inserted\s*[:=]\s*(\d+)", r"inserted\s*[:=]\s*(\d+)", r"inseridos\s*[:=]\s*(\d+)"],
        "atualizados": [r"rows_updated\s*[:=]\s*(\d+)", r"updated\s*[:=]\s*(\d+)", r"atualizados\s*[:=]\s*(\d+)"],
    }
    for key, key_patterns in patterns.items():
        values: list[int] = []
        for pattern in key_patterns:
            for match in re.findall(pattern, output, flags=re.IGNORECASE):
                try:
                    values.append(int(match))
                except Exception:
                    pass
        if values:
            summary[key] = sum(values) if key in {"inseridos", "atualizados"} and len(values) > 1 else values[-1]
    return summary


def run_script(script_name: str, args: list[str], allowed: set[str], timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        command = build_command(script_name, allowed) + list(args)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, env=env, check=False)
        duration = time.perf_counter() - started
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "duration_seconds": round(duration, 3),
            "summary": parse_summary(stdout, stderr, proc.returncode, duration),
            "stdout_tail": tail_lines(stdout, 50),
            "stderr_tail": tail_lines(stderr, 50),
            "error_message": tail_lines(stderr, 20) if proc.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = exc.stdout.decode(errors="ignore") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="ignore") if isinstance(exc.stderr, bytes) else (exc.stderr or f"Timeout após {timeout} segundos.")
        return {"status": "error", "returncode": 124, "duration_seconds": round(duration, 3), "summary": parse_summary(stdout, stderr, 124, duration), "stdout_tail": tail_lines(stdout, 50), "stderr_tail": tail_lines(stderr, 50), "error_message": tail_lines(stderr, 20)}


def market_args(operation: str, params: dict[str, Any]) -> list[str]:
    args: list[str] = []
    tickers = clean_tickers(params.get("tickers"))
    asset_class = params.get("asset_class") or "all"
    limit = safe_limit(params.get("limit"))
    incremental = bool(params.get("incremental"))
    dry_run = bool(params.get("dry_run"))
    if asset_class not in VALID_MARKET_ASSET_CLASSES:
        raise ValueError("asset_class inválido.")
    if tickers:
        args += ["--tickers", tickers]
    if limit:
        args += ["--limit", str(limit)]
    if dry_run:
        args.append("--dry-run")
    if operation in {"historical_prices", "prices_step"}:
        if asset_class != "all":
            args += ["--asset-class", str(asset_class)]
        if incremental:
            args.append("--incremental")
    elif operation in {"market_indices", "indices_step"}:
        if incremental:
            args.append("--incremental")
    return args


def run_market_operation_job(job_id: int, operation: str, params: dict[str, Any]) -> dict[str, Any]:
    script = MARKET_SCRIPT_MAP[operation]
    update_job_progress(job_id, 1, 1, f"Executando {operation}")
    run_id = start_market_run(operation, params)
    result = run_script(script, market_args(operation, params), set(MARKET_SCRIPT_MAP.values()) - {"__pipeline__"})
    finish_market_run(run_id, result["status"], result.get("summary"), result.get("stdout_tail", ""), result.get("stderr_tail", ""), result.get("error_message"))
    if result["status"] == "success":
        finish_job(job_id, result, result.get("stdout_tail"), result.get("stderr_tail"))
    else:
        fail_job(job_id, result.get("error_message") or "Operação finalizada com erro.", result.get("stdout_tail"), result.get("stderr_tail"))
    return result


def run_market_full_pipeline_job(job_id: int, params: dict[str, Any]) -> dict[str, Any]:
    steps = [
        ("prices_step", "sync_historical_prices.py"),
        ("dividends_step", "sync_dividends.py"),
        ("indices_step", "sync_market_indices.py"),
        ("macro_step", "sync_macro_indicators.py"),
        ("coverage_step", "report_data_coverage.py"),
    ]
    parent_id = start_market_run("full_pipeline", params)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    all_stdout: list[str] = []
    all_stderr: list[str] = []
    for idx, (operation, script_name) in enumerate(steps, start=1):
        row = get_job(job_id)
        if row and row["status"] == "canceled":
            break
        update_job_progress(job_id, idx - 1, len(steps), f"Rodando etapa {idx}/{len(steps)}: {operation}")
        child_id = start_market_run(operation, {**params, "triggered_by": "background_full_pipeline"}, parent_run_id=parent_id)
        args = [] if operation == "coverage_step" else market_args(operation, params)
        result = run_script(script_name, args, set(MARKET_SCRIPT_MAP.values()) - {"__pipeline__"})
        finish_market_run(child_id, result["status"], result.get("summary"), result.get("stdout_tail", ""), result.get("stderr_tail", ""), result.get("error_message"))
        results.append({"operation": operation, **result})
        all_stdout.append(f"### {operation}\n{result.get('stdout_tail', '')}")
        if result.get("stderr_tail"):
            all_stderr.append(f"### {operation}\n{result.get('stderr_tail', '')}")
        update_job_progress(job_id, idx, len(steps), f"Etapa concluída: {operation}")
    failures = sum(1 for r in results if r.get("status") != "success")
    summary = {
        "status_final": "FAILED" if failures else "SUCCESS",
        "tempo_execucao": round(time.perf_counter() - started, 3),
        "total_etapas": len(results),
        "sucesso": len(results) - failures,
        "falhas": failures,
        "steps": [{"operation": r["operation"], "status": r["status"], "duration_seconds": r.get("duration_seconds"), "error_message": r.get("error_message")} for r in results],
    }
    finish_market_run(parent_id, "error" if failures else "success", summary, "\n\n".join(all_stdout), "\n\n".join(all_stderr), "Uma ou mais etapas falharam." if failures else None)
    if failures:
        fail_job(job_id, "Uma ou mais etapas falharam.", "\n\n".join(all_stdout), "\n\n".join(all_stderr))
    else:
        finish_job(job_id, summary, "\n\n".join(all_stdout), "\n\n".join(all_stderr))
    return summary


def catalog_args(operation: str, params: dict[str, Any]) -> list[str]:
    limit = safe_limit(params.get("limit")) or 100
    asset_class = params.get("asset_class") or "all"
    if asset_class not in VALID_CATALOG_ASSET_CLASSES:
        raise ValueError("asset_class inválido.")
    args: list[str] = []
    if operation == "validate_catalog":
        args += ["--limit", str(limit), "--status", str(params.get("status") or "all"), "--max-age-days", str(int(params.get("max_age_days") or 7))]
        if asset_class != "all":
            args += ["--asset-class", asset_class]
        if params.get("force"):
            args.append("--force")
    elif operation == "update_quality":
        args += ["--limit", str(limit), "--status", str(params.get("status") or "active")]
        if asset_class != "all":
            args += ["--asset-class", asset_class]
        ticker = clean_tickers(params.get("ticker"))
        if ticker:
            args += ["--ticker", ticker.split(",")[0]]
    elif operation == "sync_assets":
        if limit:
            args += ["--limit", str(limit)]
        if asset_class != "all":
            args += ["--asset-class", asset_class]
    return args


def run_catalog_operation_job(job_id: int, operation: str, params: dict[str, Any]) -> dict[str, Any]:
    script = CATALOG_SCRIPT_MAP[operation]
    update_job_progress(job_id, 1, 1, f"Executando {operation}")
    result = run_script(script, catalog_args(operation, params), set(CATALOG_SCRIPT_MAP.values()) - {"__pipeline__"}, timeout=60 * 30)
    if result["status"] == "success":
        finish_job(job_id, result, result.get("stdout_tail"), result.get("stderr_tail"))
    else:
        fail_job(job_id, result.get("error_message") or "Operação de catálogo falhou.", result.get("stdout_tail"), result.get("stderr_tail"))
    return result


def run_catalog_full_pipeline_job(job_id: int, params: dict[str, Any]) -> dict[str, Any]:
    steps = [
        ("validate_catalog", "validate_asset_catalog.py"),
        ("update_quality", "update_asset_quality_scores.py"),
        ("sync_assets", "sync_assets_from_catalog.py"),
    ]
    results: list[dict[str, Any]] = []
    all_stdout: list[str] = []
    all_stderr: list[str] = []
    for idx, (operation, script_name) in enumerate(steps, start=1):
        row = get_job(job_id)
        if row and row["status"] == "canceled":
            break
        update_job_progress(job_id, idx - 1, len(steps), f"Rodando etapa {idx}/{len(steps)}: {operation}")
        result = run_script(script_name, catalog_args(operation, params), set(CATALOG_SCRIPT_MAP.values()) - {"__pipeline__"}, timeout=60 * 30)
        results.append({"operation": operation, **result})
        all_stdout.append(f"### {operation}\n{result.get('stdout_tail', '')}")
        if result.get("stderr_tail"):
            all_stderr.append(f"### {operation}\n{result.get('stderr_tail', '')}")
        update_job_progress(job_id, idx, len(steps), f"Etapa concluída: {operation}")
    failures = sum(1 for r in results if r.get("status") != "success")
    summary = {"total_etapas": len(results), "sucesso": len(results) - failures, "falhas": failures, "steps": results}
    if failures:
        fail_job(job_id, "Uma ou mais etapas do catálogo falharam.", "\n\n".join(all_stdout), "\n\n".join(all_stderr))
    else:
        finish_job(job_id, summary, "\n\n".join(all_stdout), "\n\n".join(all_stderr))
    return summary

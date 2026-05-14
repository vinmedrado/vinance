
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from services.background_jobs import (
    MAX_CONCURRENT_JOBS,
    can_start_job,
    fail_job,
    get_job,
    list_queued_candidates,
    mark_queue_reason,
    queue_stats,
    refresh_queued_priorities,
    start_job,
)

job_queue_lock = threading.Lock()
_job_registry: dict[int, tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = {}
_running_threads: dict[int, threading.Thread] = {}


def register_job_target(job_id: int, target_func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    _job_registry[int(job_id)] = (target_func, args, kwargs)


def run_job_async(job_id: int, target_func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """
    Registra o alvo do job e tenta processar a fila.
    O job só inicia se respeitar limite global e limite por tipo.
    """
    register_job_target(job_id, target_func, *args, **kwargs)
    process_job_queue()


def _run_registered_job(job_id: int, target_func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    try:
        row = get_job(job_id)
        if not row or row["status"] == "canceled":
            return

        # Target legado do PATCH 29 já costuma receber job_id como primeiro argumento.
        target_func(job_id, *args, **kwargs)

    except Exception as exc:
        fail_job(job_id, str(exc))
    finally:
        _running_threads.pop(job_id, None)
        _job_registry.pop(job_id, None)
        process_job_queue()


def _start_thread_for_job(job_id: int) -> bool:
    item = _job_registry.get(int(job_id))
    if not item:
        mark_queue_reason(job_id, "Aguardando executor registrado")
        return False

    if int(job_id) in _running_threads:
        return False

    if not start_job(job_id):
        # start_job já grava motivo quando bloqueado por limite.
        return False

    target_func, args, kwargs = item
    thread = threading.Thread(
        target=_run_registered_job,
        args=(int(job_id), target_func, args, kwargs),
        daemon=True,
        name=f"financeos-job-{int(job_id)}",
    )
    _running_threads[int(job_id)] = thread
    thread.start()
    return True


def process_job_queue(max_candidates: int = 10) -> int:
    """
    Processa a fila de forma local/thread-based, protegida por lock global.

    Limitação intencional:
    - Este background é local/thread-based.
    - Se o app Streamlit for fechado/reiniciado, jobs em execução podem parar.
    - Scheduler persistente/worker externo fica para patch futuro.
    """
    started = 0
    with job_queue_lock:
        refresh_queued_priorities()
        stats = queue_stats()
        if int(stats["running"]) >= MAX_CONCURRENT_JOBS:
            for row in list_queued_candidates(max_candidates):
                mark_queue_reason(int(row["id"]), "aguardando limite global")
            return started

        attempts = 0
        candidates = list_queued_candidates(max_candidates)

        for row in candidates:
            if attempts >= max_candidates:
                break
            attempts += 1

            current_stats = queue_stats()
            if int(current_stats["running"]) >= MAX_CONCURRENT_JOBS:
                mark_queue_reason(int(row["id"]), "aguardando limite global")
                break

            job_id = int(row["id"])
            job_type = str(row["job_type"])

            allowed, reason = can_start_job(job_type)
            if not allowed:
                mark_queue_reason(job_id, reason)
                continue

            if _start_thread_for_job(job_id):
                started += 1

    return started

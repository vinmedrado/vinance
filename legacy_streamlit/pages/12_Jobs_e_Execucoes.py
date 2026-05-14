
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from services.background_jobs import (
    MAX_CONCURRENT_JOBS,
    JOB_TYPE_LIMITS,
    bootstrap,
    average_duration_seconds,
    count_cleanup_candidates,
    cancel_job,
    cancel_queued_jobs,
    cleanup_old_jobs,
    get_job,
    list_jobs,
    queue_stats,
    recent_errors,
    mark_stale_running_jobs,
    get_aging_bonus_for_row,
    get_queue_wait_minutes,
)
from services.job_executor import process_job_queue
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · Jobs e Execuções", layout="wide")
inject_global_css()
bootstrap()

st.title("Jobs e Execuções")
st.caption("Acompanhe pipelines e operações longas executadas em background local.")
st.info(
    "Background local/thread-based: você pode sair desta página e a execução continuará enquanto o app Streamlit estiver aberto. "
    "Se o app for fechado/reiniciado, jobs em execução podem parar. Scheduler persistente fica para patch futuro."
)


STATUS_BADGES = {
    "queued": "🟣 queued",
    "running": "🔵 running",
    "success": "🟢 success",
    "partial_success": "🟡 Concluído com alertas",
    "failed": "🔴 failed",
    "canceled": "⚫ canceled",
}


def _safe_json(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return raw or {}



def _visual_status(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "")
    result = _safe_json(row.get("result_json"))
    if isinstance(result, dict) and result.get("execution_outcome") == "partial_success":
        return "partial_success"
    return status


def _fmt_progress(row: dict[str, Any]) -> str:
    current = int(row.get("progress_current") or 0)
    total = int(row.get("progress_total") or 0)
    if total <= 0:
        return "-"
    return f"{current}/{total} ({current / total:.0%})"


def _queued_reason(row: dict[str, Any]) -> str:
    if row.get("status") != "queued":
        return ""
    reason = row.get("queue_reason") or row.get("progress_label") or "Aguardando processamento"
    return str(reason)


def _fmt_wait_minutes(minutes: int | None) -> str:
    minutes = int(minutes or 0)
    if minutes < 60:
        return f"{minutes} min"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}min"



stats = queue_stats()

render_section_header("Resumo Operacional")
mark_stale_running_jobs()
stats = queue_stats()
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    render_metric_card("Jobs em execução", stats["running"], color="blue")
with col2:
    render_metric_card("Jobs na fila", stats["queued"], color="purple")
with col3:
    render_metric_card("Jobs com erro", stats["failed"], color="red" if stats["failed"] else "green")
with col4:
    render_metric_card("Possivelmente travados", stats.get("stale_running", 0), color="red" if stats.get("stale_running", 0) else "green")
with col5:
    render_metric_card("Tempo médio 7d", stats.get("avg_duration_seconds_7d") or "-", color="blue")

with st.expander("Ver limites e aging da fila"):
    st.json({
        "job_type_limits": JOB_TYPE_LIMITS,
        "aging_interval_minutes": stats.get("aging_interval_minutes"),
        "aging_bonus_max": stats.get("aging_bonus_max"),
        "aging_recalc_interval_seconds": 30,
        "stale_running_seconds": 7200,
    })

a1, a2, a3 = st.columns(3)
with a1:
    if st.button("Atualizar status", use_container_width=True):
        mark_stale_running_jobs()
        process_job_queue()
        st.rerun()
with a2:
    if st.button("Cancelar jobs na fila", use_container_width=True):
        total = cancel_queued_jobs()
        process_job_queue()
        st.warning(f"{total} job(s) queued foram cancelados.")
        st.rerun()
with a3:
    cleanup_candidates = count_cleanup_candidates(30)
    confirm_cleanup = st.checkbox(f"Confirmo limpar histórico antigo ({cleanup_candidates} job(s))", value=False)
    if st.button("Limpar histórico antigo", use_container_width=True):
        if not confirm_cleanup:
            st.warning("Marque a confirmação antes de limpar o histórico antigo.")
        else:
            removed = cleanup_old_jobs(30)
            st.success(f"{removed} job(s) antigo(s) removido(s).")
            st.rerun()


render_section_header("Observabilidade")
err_rows = [dict(row) for row in recent_errors(5)]
if err_rows:
    with st.expander("Últimos erros", expanded=False):
        for err in err_rows:
            st.error(f"Job #{err.get('id')} · {err.get('job_type')} · {err.get('finished_at')}")
            st.code(err.get("error_message") or "", language="text")
else:
    st.success("Nenhum erro recente encontrado.")

render_section_header("Filtros")
all_recent = [dict(row) for row in list_jobs(limit=300)]
f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    status_filter = st.selectbox("Filtrar status", ["all", "queued", "running", "success", "failed", "canceled"], index=0)
with f2:
    available_types = sorted({str(r["job_type"]) for r in all_recent})
    job_type_filter = st.selectbox("Filtrar job_type", ["all", *available_types], index=0)
with f3:
    limit = st.number_input("Quantidade", min_value=10, max_value=500, value=50, step=10)

rows = [dict(row) for row in list_jobs(limit=int(limit), status=status_filter, job_type=job_type_filter)]

render_section_header("Jobs recentes")
if not rows:
    st.info("Nenhum job encontrado para os filtros atuais.")
else:
    table = pd.DataFrame(
        [
            {
                "id": r.get("id"),
                "job_type": r.get("job_type"),
                "status": STATUS_BADGES.get(_visual_status(r), _visual_status(r)),
                "priority": r.get("priority", 0),
                "effective_priority": r.get("effective_priority", r.get("priority", 0)),
                "aging_bonus": get_aging_bonus_for_row(r),
                "tempo_fila": _fmt_wait_minutes(get_queue_wait_minutes(r)) if r.get("status") == "queued" else "",
                "created_at": r.get("created_at"),
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "duration_seconds": r.get("duration_seconds"),
                "progresso": _fmt_progress(r),
                "progress_label": r.get("progress_label"),
                "motivo_fila": _queued_reason(r),
                "stale_running": bool(r.get("is_stale_running")),
                "erro": r.get("error_message"),
            }
            for r in rows
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    selected = st.selectbox("Selecionar job para detalhes", [int(r["id"]) for r in rows], format_func=lambda x: f"Job #{x}")
    job = get_job(int(selected))
    if job:
        item = dict(job)
        st.subheader(f"Detalhes do Job #{item['id']}")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            render_metric_card("Status", STATUS_BADGES.get(_visual_status(item), _visual_status(item)), color="green" if _visual_status(item) == "success" else "yellow" if _visual_status(item) == "partial_success" else "red" if _visual_status(item) == "failed" else "blue")
        with c2:
            render_metric_card("Tipo", item["job_type"], color="purple")
        with c3:
            render_metric_card("Prioridade", item.get("priority", 0), color="green")
        with c4:
            render_metric_card("Prioridade efetiva", item.get("effective_priority", item.get("priority", 0)), color="purple")
        with c5:
            render_metric_card("Aging bonus", get_aging_bonus_for_row(item), color="blue")
        with c6:
            render_metric_card("Progresso", _fmt_progress(item), color="green")

        if item.get("status") == "queued":
            wait_minutes = get_queue_wait_minutes(item)
            aging_bonus = get_aging_bonus_for_row(item)
            st.warning(f"Motivo na fila: {item.get('queue_reason') or item.get('progress_label') or 'aguardando execução'}")
            if wait_minutes >= int(stats.get("aging_interval_minutes") or 10):
                st.info(f"Job aguardando há {_fmt_wait_minutes(wait_minutes)} — prioridade efetiva aumentada em +{aging_bonus}.")
        if item.get("status") == "running" and int(item.get("is_stale_running") or 0) == 1:
            st.error("Job possivelmente travado: está em execução há mais de 2 horas. Nenhuma interrupção automática foi feita.")

        if _visual_status(item) == "partial_success":
            st.warning("Concluído com alertas: o job terminou, mas o resultado do orquestrador teve falhas não críticas ou alertas.")

        total = int(item.get("progress_total") or 0)
        current = int(item.get("progress_current") or 0)
        if total > 0:
            st.progress(min(current / total, 1.0), text=item.get("progress_label") or "Executando")
        elif item.get("status") == "running":
            st.spinner(item.get("progress_label") or "Executando...")

        d1, d2 = st.columns(2)
        with d1:
            if item["status"] in ("queued", "running"):
                if st.button("Marcar como cancelado", use_container_width=True):
                    if cancel_job(int(item["id"])):
                        process_job_queue()
                        st.warning("Job marcado como cancelado.")
                        st.rerun()
                    else:
                        st.info("Esse job não pode mais ser cancelado.")
        with d2:
            if st.button("Tentar processar fila agora", use_container_width=True):
                started = process_job_queue()
                st.success(f"{started} job(s) iniciado(s) pela fila.")
                st.rerun()

        with st.expander("Parâmetros"):
            st.json(_safe_json(item.get("parameters_json")))

        with st.expander("Resultado"):
            st.json(_safe_json(item.get("result_json")))

        with st.expander("Logs da fila"):
            result = _safe_json(item.get("result_json"))
            events = result.get("_queue_events") if isinstance(result, dict) else None
            if events:
                st.json(events)
            else:
                st.info("Nenhum evento de fila registrado.")

        with st.expander("stdout_tail"):
            st.code(item.get("stdout_tail") or "", language="text")

        with st.expander("stderr_tail"):
            st.code(item.get("stderr_tail") or "", language="text")

        if item.get("error_message"):
            with st.expander("Erro"):
                st.code(item["error_message"], language="text")

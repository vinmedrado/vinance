from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
import streamlit as st

from services.background_jobs import bootstrap as bootstrap_jobs
from services.background_jobs import create_job, get_job, list_jobs
from services.job_executor import run_job_async
from services.market_data_pipeline_runs import bootstrap, finish_run, get_child_runs, get_recent_runs, start_run
from services.pipeline_background_tasks import MARKET_SCRIPT_MAP, market_args, run_market_full_pipeline_job, run_market_operation_job, run_script
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
HEAVY_LIMIT = 1000
VALID_ASSET_CLASSES = ["all", "equity", "fii", "etf", "bdr", "crypto", "currency", "commodity", "index"]

OPERATION_LABELS = {
    "historical_prices": "Histórico de Preços",
    "dividends": "Dividendos",
    "market_indices": "Índices / Benchmarks",
    "macro_indicators": "Macro / CDI",
    "data_coverage_report": "Relatório de Cobertura",
    "full_pipeline": "Pipeline Completo de Dados",
    "prices_step": "Etapa: Preços",
    "dividends_step": "Etapa: Dividendos",
    "indices_step": "Etapa: Índices",
    "macro_step": "Etapa: Macro/CDI",
    "coverage_step": "Etapa: Relatório de Cobertura",
}

st.set_page_config(page_title="FinanceOS · Automação de Dados de Mercado", layout="wide")
inject_global_css()
bootstrap()
bootstrap_jobs()

st.title("Automação de Dados de Mercado")
st.caption("Atualize preços, dividendos, índices, macro/CDI e cobertura pela interface, com execução síncrona ou background local.")
st.info("Background local/thread-based: você pode sair desta página e a execução continua enquanto o app Streamlit estiver aberto. Se o app for fechado/reiniciado, jobs em execução podem parar.")


def _format_duration(seconds: Any) -> str:
    try:
        total = int(float(seconds or 0))
    except Exception:
        total = 0
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _safe_limit(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("limit deve ser maior ou igual a 0.")
    return parsed or None


def _is_heavy(limit: int | None) -> bool:
    return limit is None or int(limit or 0) > HEAVY_LIMIT


def _show_result(result: dict[str, Any], operation: str) -> None:
    label = OPERATION_LABELS.get(operation, operation)
    status = result.get("status")
    summary = result.get("summary") or result
    if status == "success":
        st.success(f"{label} concluído com sucesso em {_format_duration(result.get('duration_seconds'))}.")
    else:
        st.error(f"{label} finalizado com erro em {_format_duration(result.get('duration_seconds'))}.")
    cols = st.columns(6)
    metrics = [
        ("Status", summary.get("status_final") or status),
        ("Processados", summary.get("total_processado", "-")),
        ("Sucesso", summary.get("sucesso", "-")),
        ("Falhas", summary.get("falhas", "-")),
        ("Inseridos", summary.get("inseridos", "-")),
        ("Atualizados", summary.get("atualizados", "-")),
    ]
    for idx, (k, v) in enumerate(metrics):
        with cols[idx]:
            render_metric_card(k, v, color="green" if status == "success" else "red")
    with st.expander("Ver log completo"):
        if result.get("stdout_tail"):
            st.markdown("**stdout — últimas 50 linhas**")
            st.code(result["stdout_tail"], language="text")
        if result.get("stderr_tail"):
            st.markdown("**stderr — últimas 50 linhas**")
            st.code(result["stderr_tail"], language="text")
        if not result.get("stdout_tail") and not result.get("stderr_tail"):
            st.info("Nenhum log retornado pelo script.")
    with st.expander("Ver parâmetros"):
        st.json(result.get("params") or {})


def _run_sync_operation(operation: str, params: dict[str, Any]) -> dict[str, Any]:
    script = MARKET_SCRIPT_MAP[operation]
    args = market_args(operation, params)
    run_id = start_run(operation, params)
    result = run_script(script, args, set(MARKET_SCRIPT_MAP.values()))
    finish_run(run_id, result["status"], result.get("summary"), result.get("stdout_tail", ""), result.get("stderr_tail", ""), result.get("error_message"))
    result["params"] = params
    return result


def _submit_background(operation: str, params: dict[str, Any], full_pipeline: bool = False, priority: int = 0) -> int | None:
    job_type = "market_data_full_pipeline" if full_pipeline else f"market_data_{operation}"
    try:
        job_id = create_job(job_type, params, priority=priority)
    except Exception as exc:
        st.warning(str(exc))
        return None
    if full_pipeline:
        run_job_async(job_id, run_market_full_pipeline_job, params)
    else:
        run_job_async(job_id, run_market_operation_job, operation, params)
    return job_id


def _operation_card(operation: str, label: str, show_tickers: bool, show_asset_class: bool, show_incremental: bool) -> None:
    with st.container(border=True):
        st.subheader(label)
        tickers = st.text_input(f"Tickers opcional — {label}", key=f"{operation}_tickers", placeholder="PETR4.SA, ITUB4.SA") if show_tickers else ""
        asset_class = st.selectbox(f"asset_class — {label}", VALID_ASSET_CLASSES, key=f"{operation}_asset", index=0) if show_asset_class else "all"
        limit = st.number_input(f"limit — {label}", min_value=0, max_value=100000, value=100, step=50, key=f"{operation}_limit")
        incremental = st.checkbox(f"incremental — {label}", value=True, key=f"{operation}_incremental") if show_incremental else False
        dry_run = st.checkbox(f"dry_run — {label}", value=False, key=f"{operation}_dry")
        background = st.checkbox(f"Executar em background — {label}", value=False, key=f"{operation}_background")
        heavy = _is_heavy(_safe_limit(limit))
        confirm_heavy = True
        if heavy:
            st.warning("Operação potencialmente pesada: limit vazio/zero ou maior que 1000 pode demorar vários minutos.")
            confirm_heavy = st.checkbox("Confirmo execução pesada (pode demorar vários minutos)", key=f"{operation}_heavy_confirm")
        if st.button(label, use_container_width=True, key=f"btn_{operation}"):
            if heavy and not confirm_heavy:
                st.warning("Marque a confirmação de execução pesada antes de continuar.")
                return
            params = {"tickers": tickers, "asset_class": asset_class, "limit": _safe_limit(limit), "incremental": bool(incremental), "dry_run": bool(dry_run)}
            if background:
                job_id = _submit_background(operation, params)
                if job_id:
                    st.success(f"Job #{job_id} criado em background.")
                st.info("Use o botão Atualizar status ou a página Jobs e Execuções para acompanhar.")
            else:
                with st.spinner(f"Executando {label}..."):
                    result = _run_sync_operation(operation, params)
                _show_result(result, operation)


render_section_header("Operações disponíveis")
col1, col2 = st.columns(2)
with col1:
    _operation_card("historical_prices", "Atualizar Histórico de Preços", True, True, True)
with col2:
    _operation_card("dividends", "Atualizar Dividendos", True, False, False)
col3, col4 = st.columns(2)
with col3:
    _operation_card("market_indices", "Atualizar Índices", False, False, True)
with col4:
    _operation_card("macro_indicators", "Atualizar Macro/CDI", False, False, False)

st.divider()
render_section_header("Pipeline Completo de Dados")
with st.container(border=True):
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        pipe_asset_class = st.selectbox("asset_class", VALID_ASSET_CLASSES, index=0, key="pipe_asset_class")
    with p2:
        pipe_limit = st.number_input("limit", min_value=0, max_value=100000, value=100, step=50, key="pipe_limit")
    with p3:
        pipe_incremental = st.checkbox("incremental", value=True, key="pipe_incremental")
    with p4:
        pipe_dry_run = st.checkbox("dry_run", value=False, key="pipe_dry_run")
    run_background = st.checkbox("Executar em background", value=True, key="pipe_background")
    confirm_pipeline = st.checkbox("Confirmo que desejo rodar o pipeline completo de dados.", key="pipe_confirm")
    heavy = _is_heavy(_safe_limit(pipe_limit))
    confirm_heavy = True
    if heavy:
        st.warning("Pipeline potencialmente pesado: limit vazio/zero ou maior que 1000 pode demorar vários minutos.")
        confirm_heavy = st.checkbox("Confirmo execução pesada (pode demorar vários minutos)", key="pipe_confirm_heavy")

    if st.button("Rodar Pipeline Completo de Dados", type="primary", use_container_width=True):
        if not confirm_pipeline:
            st.warning("Confirme que deseja rodar o pipeline completo antes de continuar.")
        elif heavy and not confirm_heavy:
            st.warning("Marque a confirmação de execução pesada antes de continuar.")
        else:
            params = {"asset_class": pipe_asset_class, "limit": _safe_limit(pipe_limit), "incremental": bool(pipe_incremental), "dry_run": bool(pipe_dry_run)}
            if run_background:
                job_id = _submit_background("full_pipeline", params, full_pipeline=True)
                if job_id:
                    st.success(f"Pipeline completo enviado para background. Job #{job_id}.")
            else:
                from services.pipeline_background_tasks import run_market_full_pipeline_job
                temp_job = create_job("market_data_full_pipeline_sync", params)
                with st.spinner("Rodando pipeline completo..."):
                    summary = run_market_full_pipeline_job(temp_job, params)
                st.subheader("Resumo do Pipeline")
                r1, r2, r3, r4, r5 = st.columns(5)
                failures = int(summary.get("falhas") or 0)
                with r1: render_metric_card("Status geral", summary.get("status_final"), color="red" if failures else "green")
                with r2: render_metric_card("Tempo total", _format_duration(summary.get("tempo_execucao")), color="blue")
                with r3: render_metric_card("Etapas", summary.get("total_etapas"), color="purple")
                with r4: render_metric_card("Sucesso", summary.get("sucesso"), color="green")
                with r5: render_metric_card("Falhas", summary.get("falhas"), color="red" if failures else "green")

st.divider()
render_section_header("Jobs de dados de mercado")
if st.button("Atualizar status", use_container_width=True):
    st.rerun()
job_rows = list_jobs(limit=10, job_type=None)
market_jobs = [dict(r) for r in job_rows if str(r["job_type"]).startswith("market_data")]
if market_jobs:
    cards = st.columns(3)
    running = sum(1 for r in market_jobs if r["status"] == "running")
    done = sum(1 for r in market_jobs if r["status"] == "success")
    failed = sum(1 for r in market_jobs if r["status"] == "failed")
    with cards[0]: render_metric_card("Jobs em execução", running, color="blue")
    with cards[1]: render_metric_card("Jobs concluídos", done, color="green")
    with cards[2]: render_metric_card("Jobs com erro", failed, color="red" if failed else "green")
    st.dataframe(pd.DataFrame([{
        "id": r["id"], "job_type": r["job_type"], "status": r["status"], "created_at": r["created_at"],
        "duration_seconds": r["duration_seconds"], "progress": f"{r['progress_current'] or 0}/{r['progress_total'] or 0}", "label": r["progress_label"],
    } for r in market_jobs]), use_container_width=True, hide_index=True)
else:
    st.info("Nenhum job de dados de mercado registrado ainda.")

st.divider()
render_section_header("Histórico recente", "Por padrão, aparecem apenas execuções principais. Detalhes do pipeline ficam dentro da execução principal.")
with st.expander("Ver histórico recente", expanded=True):
    rows = get_recent_runs(30, main_only=True)
    if not rows:
        st.info("Nenhuma execução registrada ainda.")
    else:
        display_rows = []
        for row in rows:
            item = dict(row)
            try:
                summary = json.loads(item.get("result_summary_json") or "{}")
            except Exception:
                summary = {}
            display_rows.append({
                "id": item.get("id"), "operation": OPERATION_LABELS.get(item.get("operation"), item.get("operation")),
                "status": item.get("status"), "started_at": item.get("started_at"), "finished_at": item.get("finished_at"),
                "duration_seconds": item.get("duration_seconds"), "sucesso": summary.get("sucesso"), "falhas": summary.get("falhas"),
                "error_message": item.get("error_message"),
            })
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
        for row in rows:
            item = dict(row)
            if item.get("operation") == "full_pipeline":
                with st.expander(f"Ver detalhes da execução #{item.get('id')} — {item.get('started_at')}"):
                    children = get_child_runs(int(item["id"]))
                    if not children:
                        st.info("Nenhuma sub-etapa registrada para esta execução.")
                    else:
                        child_rows = []
                        for child in children:
                            ch = dict(child)
                            child_rows.append({"etapa": OPERATION_LABELS.get(ch.get("operation"), ch.get("operation")), "status": ch.get("status"), "duration_seconds": ch.get("duration_seconds"), "erro": ch.get("error_message")})
                        st.dataframe(pd.DataFrame(child_rows), use_container_width=True, hide_index=True)
                        for child in children:
                            ch = dict(child)
                            with st.expander(f"Logs — {OPERATION_LABELS.get(ch.get('operation'), ch.get('operation'))}"):
                                if ch.get("stdout_tail"):
                                    st.code(ch["stdout_tail"], language="text")
                                if ch.get("stderr_tail"):
                                    st.code(ch["stderr_tail"], language="text")

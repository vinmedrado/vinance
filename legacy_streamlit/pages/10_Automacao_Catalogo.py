from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from services.background_jobs import bootstrap as bootstrap_jobs
from services.background_jobs import create_job, list_jobs
from services.catalog_pipeline_runs import bootstrap, finish_run, get_recent_runs, start_run
from services.job_executor import run_job_async
from services.pipeline_background_tasks import catalog_args, run_catalog_full_pipeline_job, run_catalog_operation_job, run_script
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
ROOT = Path(__file__).resolve().parents[1]
IMPORTS_DIR = ROOT / "data" / "imports"
VALID_CLASSES = ["all", "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity", "unknown"]
CATALOG_SCRIPTS = {"validate_asset_catalog.py", "update_asset_quality_scores.py", "sync_assets_from_catalog.py", "import_asset_catalog_from_excel.py", "sync_crypto_catalog.py"}

st.set_page_config(page_title="FinanceOS · Automação do Catálogo", layout="wide")
inject_global_css()
bootstrap()
bootstrap_jobs()

st.title("Automação do Catálogo")
st.caption("Gerencie asset_catalog pela interface Streamlit, com opção de background local para operações pesadas.")
st.info("Background local/thread-based: a execução continua enquanto o app Streamlit estiver aberto. Se o app for fechado/reiniciado, jobs em execução podem parar.")


def _show_result(result: dict[str, Any]) -> None:
    status = result.get("status")
    duration = float(result.get("duration_seconds") or 0)
    if status == "success":
        st.success(f"Operação concluída com sucesso em {duration:.2f}s.")
    else:
        st.error(f"Operação finalizada com erro em {duration:.2f}s.")
    summary = result.get("summary") or result
    cols = st.columns(4)
    with cols[0]: render_metric_card("Status", summary.get("status_final", status), color="green" if status == "success" else "red")
    with cols[1]: render_metric_card("Processados", summary.get("total_processado", "-"), color="blue")
    with cols[2]: render_metric_card("Sucesso", summary.get("sucesso", "-"), color="green")
    with cols[3]: render_metric_card("Falhas", summary.get("falhas", "-"), color="red" if status != "success" else "green")
    with st.expander("Logs resumidos"):
        if result.get("stdout_tail"):
            st.code(result["stdout_tail"], language="text")
        if result.get("stderr_tail"):
            st.code(result["stderr_tail"], language="text")


def _run_catalog_sync(operation: str, script: str, args: list[str], params: dict[str, Any]) -> dict[str, Any]:
    run_id = start_run(operation, params)
    result = run_script(script, args, CATALOG_SCRIPTS, timeout=60 * 30)
    finish_run(run_id, result["status"], result, result.get("error_message"))
    return result


def _submit_background(operation: str, params: dict[str, Any], full_pipeline: bool = False, priority: int = 0) -> int | None:
    job_type = "catalog_full_pipeline" if full_pipeline else f"catalog_{operation}"
    try:
        job_id = create_job(job_type, params, priority=priority)
    except Exception as exc:
        st.warning(str(exc))
        return None
    if full_pipeline:
        run_job_async(job_id, run_catalog_full_pipeline_job, params)
    else:
        run_job_async(job_id, run_catalog_operation_job, operation, params)
    return job_id


def _arg_if_value(flag: str, value: Any) -> list[str]:
    if value in (None, "", "all"):
        return []
    return [flag, str(value)]


render_section_header("Operações do Catálogo")

with st.container(border=True):
    st.subheader("A. Importar Excel Seed")
    uploaded = st.file_uploader("Selecione um arquivo .xlsx", type=["xlsx"], accept_multiple_files=False)
    if st.button("Importar Excel Seed", use_container_width=True):
        if uploaded is None:
            st.warning("Envie um arquivo .xlsx antes de importar.")
        else:
            IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded.name)
            temp_path = IMPORTS_DIR / f"streamlit_seed_{int(time.time())}_{safe_name}"
            temp_path.write_bytes(uploaded.getbuffer())
            try:
                with st.spinner("Importando Excel seed..."):
                    result = _run_catalog_sync("import_excel_seed", "import_asset_catalog_from_excel.py", ["--file", str(temp_path.relative_to(ROOT))], {"file": uploaded.name})
                _show_result(result)
            finally:
                temp_path.unlink(missing_ok=True)

st.divider()
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("B. Sincronizar Criptos")
        crypto_limit = st.number_input("Limit criptos", min_value=1, max_value=5000, value=100, step=25)
        if st.button("Sincronizar Criptos", use_container_width=True):
            with st.spinner("Sincronizando criptos..."):
                result = _run_catalog_sync("sync_crypto", "sync_crypto_catalog.py", ["--limit", str(int(crypto_limit))], {"limit": int(crypto_limit)})
            _show_result(result)

with col2:
    with st.container(border=True):
        st.subheader("E. Sincronizar Assets")
        sync_limit = st.number_input("Limit sync assets", min_value=0, max_value=100000, value=0, step=50)
        sync_class = st.selectbox("asset_class sync", VALID_CLASSES, index=0)
        sync_background = st.checkbox("Executar em background — sincronizar assets", value=False)
        if st.button("Sincronizar Ativos Validados", use_container_width=True):
            params = {"limit": int(sync_limit) or None, "asset_class": sync_class}
            if sync_background:
                job_id = _submit_background("sync_assets", params)
                st.success(f"Job #{job_id} criado em background.")
            else:
                with st.spinner("Sincronizando ativos..."):
                    result = _run_catalog_sync("sync_assets", "sync_assets_from_catalog.py", catalog_args("sync_assets", params), params)
                _show_result(result)

st.divider()
col3, col4 = st.columns(2)
with col3:
    with st.container(border=True):
        st.subheader("C. Validar Catálogo")
        validate_limit = st.number_input("Limit validação", min_value=1, max_value=10000, value=100, step=50)
        validate_class = st.selectbox("asset_class validação", VALID_CLASSES, index=0)
        validate_status = st.selectbox("status validação", ["pending_validation", "all", "active", "weak_data", "stale", "not_found", "unsupported", "error"], index=0)
        validate_max_age = st.number_input("max_age_days", min_value=0, max_value=365, value=7, step=1)
        validate_force = st.checkbox("force", value=False)
        validate_background = st.checkbox("Executar em background — validar catálogo", value=False)
        if st.button("Validar Catálogo", use_container_width=True):
            params = {"limit": int(validate_limit), "asset_class": validate_class, "status": validate_status, "max_age_days": int(validate_max_age), "force": bool(validate_force)}
            if validate_background:
                job_id = _submit_background("validate_catalog", params)
                st.success(f"Job #{job_id} criado em background.")
            else:
                with st.spinner("Validando catálogo..."):
                    result = _run_catalog_sync("validate_catalog", "validate_asset_catalog.py", catalog_args("validate_catalog", params), params)
                _show_result(result)

with col4:
    with st.container(border=True):
        st.subheader("D. Atualizar Scores de Qualidade")
        quality_limit = st.number_input("Limit qualidade", min_value=1, max_value=10000, value=500, step=50)
        quality_class = st.selectbox("asset_class qualidade", VALID_CLASSES, index=0)
        quality_status = st.selectbox("status qualidade", ["all", "active", "weak_data", "pending_validation", "stale", "error"], index=1)
        quality_ticker = st.text_input("ticker específico", value="")
        quality_background = st.checkbox("Executar em background — atualizar qualidade", value=False)
        if st.button("Atualizar Qualidade", use_container_width=True):
            params = {"limit": int(quality_limit), "asset_class": quality_class, "status": quality_status, "ticker": quality_ticker.strip().upper()}
            if quality_background:
                job_id = _submit_background("update_quality", params)
                st.success(f"Job #{job_id} criado em background.")
            else:
                with st.spinner("Atualizando qualidade..."):
                    result = _run_catalog_sync("update_quality", "update_asset_quality_scores.py", catalog_args("update_quality", params), params)
                _show_result(result)

st.divider()
with st.container(border=True):
    st.subheader("F. Pipeline Completo")
    st.caption("Executa validação do catálogo, atualização dos scores de qualidade e sincronização asset_catalog → assets.")
    p1, p2, p3 = st.columns(3)
    with p1:
        pipeline_limit = st.number_input("Limit pipeline", min_value=1, max_value=10000, value=500, step=50)
    with p2:
        pipeline_asset_class = st.selectbox("asset_class pipeline", VALID_CLASSES, index=0)
    with p3:
        pipeline_force = st.checkbox("force pipeline", value=False)
    pipeline_background = st.checkbox("Executar em background — pipeline completo", value=True)
    if st.button("Rodar Pipeline Completo", use_container_width=True, type="primary"):
        params = {"limit": int(pipeline_limit), "asset_class": pipeline_asset_class, "force": bool(pipeline_force), "status": "all", "max_age_days": 7}
        if pipeline_background:
            job_id = _submit_background("catalog_full_pipeline", params, full_pipeline=True)
            if job_id:
                st.success(f"Pipeline do catálogo enviado para background. Job #{job_id}.")
        else:
            temp_job = create_job("catalog_full_pipeline_sync", params)
            with st.spinner("Rodando pipeline do catálogo..."):
                summary = run_catalog_full_pipeline_job(temp_job, params)
            failures = int(summary.get("falhas") or 0)
            if failures:
                st.error("Pipeline finalizado com falhas. Veja logs em Jobs e Execuções.")
            else:
                st.success("Pipeline finalizado com sucesso.")
            st.json(summary)

st.divider()
render_section_header("Jobs do catálogo")
if st.button("Atualizar status dos jobs", use_container_width=True):
    st.rerun()
all_jobs = [dict(r) for r in list_jobs(limit=20) if str(r["job_type"]).startswith("catalog")]
if all_jobs:
    c1, c2, c3 = st.columns(3)
    with c1: render_metric_card("Em execução", sum(1 for r in all_jobs if r["status"] == "running"), color="blue")
    with c2: render_metric_card("Concluídos", sum(1 for r in all_jobs if r["status"] == "success"), color="green")
    with c3: render_metric_card("Com erro", sum(1 for r in all_jobs if r["status"] == "failed"), color="red")
    st.dataframe(pd.DataFrame([{"id": r["id"], "job_type": r["job_type"], "status": r["status"], "created_at": r["created_at"], "duration_seconds": r["duration_seconds"], "progresso": f"{r['progress_current'] or 0}/{r['progress_total'] or 0}", "label": r["progress_label"]} for r in all_jobs]), use_container_width=True, hide_index=True)
else:
    st.info("Nenhum job do catálogo registrado ainda.")

st.divider()
render_section_header("Histórico de Execuções")
runs = get_recent_runs(30)
if runs:
    df = pd.DataFrame([dict(row) for row in runs])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma execução registrada ainda.")

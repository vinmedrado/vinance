
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from services.background_jobs import bootstrap as bootstrap_jobs
from services.background_jobs import create_job, get_job
from services.financeos_orchestrator import (
    bootstrap as bootstrap_orchestrator,
    get_orchestrator_run,
    get_orchestrator_steps,
    get_recent_orchestrator_runs,
    run_orchestrator_job,
)
from services.job_executor import run_job_async
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · Orquestrador Geral", layout="wide")
inject_global_css()
bootstrap_jobs()
bootstrap_orchestrator()

st.title("Orquestrador Geral")
st.caption("Execute o ciclo completo do FinanceOS em uma única operação.")
st.info("Execução local/thread-based via sistema de jobs. Se o Streamlit for fechado/reiniciado, jobs em execução podem parar.")

MODE_OPTIONS = {
    "rápido": "rapido",
    "completo": "completo",
    "pesquisa": "pesquisa",
}
PRIORITY_BY_MODE = {
    "pesquisa": 8,
    "completo": 6,
    "rapido": 4,
}
VALID_ASSET_CLASSES = ["all", "equity", "fii", "etf", "bdr", "crypto", "currency", "commodity", "index", "unknown"]


def _safe_json(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return raw or {}


def _fmt_duration(seconds: Any) -> str:
    try:
        total = int(float(seconds or 0))
    except Exception:
        total = 0
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _is_heavy(mode: str, force: bool, limit: int | None) -> bool:
    return mode in {"completo", "pesquisa"} or bool(force) or limit is None or int(limit or 0) > 1000


def _create_orchestrator_job(params: dict[str, Any]) -> int | None:
    priority = PRIORITY_BY_MODE.get(params["mode"], 4)
    try:
        job_id = create_job("financeos_orchestrator", params, priority=priority)
    except Exception as exc:
        st.warning(str(exc))
        return None
    run_job_async(job_id, run_orchestrator_job, params)
    return job_id


render_section_header("Configuração da execução")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        mode_label = st.selectbox("Modo", list(MODE_OPTIONS.keys()), index=0)
        mode = MODE_OPTIONS[mode_label]
        asset_class = st.selectbox("asset_class", VALID_ASSET_CLASSES, index=0)
        limit = st.number_input("limit", min_value=0, max_value=100000, value=200, step=50)
    with c2:
        max_age_days = st.number_input("max_age_days", min_value=0, max_value=365, value=7, step=1)
        top_n = st.number_input("top_n", min_value=0, max_value=10000, value=50, step=10)
        initial_capital = st.number_input("initial_capital", min_value=1.0, value=10000.0, step=1000.0)
    with c3:
        force = st.checkbox("force", value=False)
        dry_run = st.checkbox("dry_run", value=False)
        incremental = st.checkbox("incremental", value=True)
        run_backtest = st.checkbox("run_backtest", value=False)
        retry_non_critical_steps = st.checkbox("retry_non_critical_steps", value=True)

    d1, d2 = st.columns(2)
    with d1:
        start_date = st.text_input("start_date opcional (YYYY-MM-DD)", value="")
    with d2:
        end_date = st.text_input("end_date opcional (YYYY-MM-DD)", value="")

    params = {
        "mode": mode,
        "asset_class": asset_class,
        "limit": int(limit) if int(limit) > 0 else None,
        "max_age_days": int(max_age_days),
        "force": bool(force),
        "dry_run": bool(dry_run),
        "incremental": bool(incremental),
        "run_backtest": bool(run_backtest),
        "retry_non_critical_steps": bool(retry_non_critical_steps),
        "top_n": int(top_n),
        "start_date": start_date.strip(),
        "end_date": end_date.strip(),
        "initial_capital": float(initial_capital),
    }

    if mode == "pesquisa":
        st.error("Modo Pesquisa executa pipeline completo + análise + backtest. Pode demorar bastante.")
        confirm_research = st.checkbox("Confirmo execução em modo pesquisa.", value=False)
    else:
        confirm_research = True

    heavy = _is_heavy(mode, force, params["limit"])
    confirm_heavy = True
    if heavy:
        st.warning("Essa execução pode ser pesada. Confirme antes de rodar.")
        confirm_heavy = st.checkbox("Confirmo execução pesada.", value=False)

    with st.expander("Ver parâmetros"):
        st.json(params)

    if st.button("Rodar Orquestrador", type="primary", use_container_width=True):
        if mode == "pesquisa" and not confirm_research:
            st.warning("Marque “Confirmo execução em modo pesquisa.” antes de continuar.")
        elif heavy and not confirm_heavy:
            st.warning("Marque “Confirmo execução pesada.” antes de continuar.")
        else:
            job_id = _create_orchestrator_job(params)
            if job_id:
                st.success(f"Orquestrador enviado para background. Job #{job_id}.")
                st.info("Acompanhe por aqui ou pela página Jobs e Execuções.")

render_section_header("Histórico recente")
runs = [dict(r) for r in get_recent_orchestrator_runs(20)]

if not runs:
    st.info("Nenhuma execução do orquestrador registrada ainda.")
else:
    last = runs[0]
    result = _safe_json(last.get("result_json"))
    success_steps = result.get("sucesso", "-") if isinstance(result, dict) else "-"
    failed_steps = result.get("falhas", "-") if isinstance(result, dict) else "-"

    warning_steps = result.get("warning_steps", "-") if isinstance(result, dict) else "-"
    final_message = result.get("final_message", "") if isinstance(result, dict) else ""

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Última execução", f"#{last['id']}", color="blue")
    with c2:
        render_metric_card("Status geral", result.get("status", last.get("status")) if isinstance(result, dict) else last.get("status"), color="green" if (result.get("status") if isinstance(result, dict) else last.get("status")) == "success" else "yellow" if (result.get("status") if isinstance(result, dict) else last.get("status")) in ("partial_success", "warning") else "red" if last.get("status") == "failed" else "purple")
    with c3:
        render_metric_card("Tempo total", _fmt_duration(result.get("duration_seconds", last.get("duration_seconds")) if isinstance(result, dict) else last.get("duration_seconds")), color="blue")
    with c4:
        render_metric_card("Concluídas", success_steps, color="green")
    with c5:
        render_metric_card("Erro/Alerta", f"{failed_steps} erro · {warning_steps} alerta", color="red" if failed_steps not in (0, "0", "-") else "purple" if warning_steps not in (0, "0", "-") else "green")

    if final_message:
        _status_exec = result.get("status") if isinstance(result, dict) else last.get("status")
        if _status_exec == "partial_success":
            st.warning("Execução concluída com alertas. Verifique etapas com falha parcial.")
            st.warning(final_message)
        elif failed_steps not in (0, "0", "-"):
            st.error(final_message)
        elif warning_steps not in (0, "0", "-"):
            st.warning(final_message)
        else:
            st.success(final_message)

    table = pd.DataFrame(
        [
            {
                "id": r.get("id"),
                "job_id": r.get("job_id"),
                "mode": r.get("mode"),
                "status": r.get("status"),
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "duration_seconds": r.get("duration_seconds"),
                "error_message": r.get("error_message"),
            }
            for r in runs
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    selected = st.selectbox("Selecionar execução", [int(r["id"]) for r in runs], format_func=lambda x: f"Execução #{x}")
    run = get_orchestrator_run(int(selected))
    if run:
        run_dict = dict(run)
        st.subheader(f"Execução #{run_dict['id']}")

        job_id = run_dict.get("job_id")
        if job_id:
            job = get_job(int(job_id))
            if job:
                job = dict(job)
                total = int(job.get("progress_total") or 0)
                current = int(job.get("progress_current") or 0)
                if total:
                    st.progress(min(current / total, 1.0), text=job.get("progress_label") or "Executando")
                render_metric_card("Job", f"#{job_id} · {job.get('status')}", color="blue")

        executive = _safe_json(run_dict.get("result_json"))
        if isinstance(executive, dict):
            st.markdown("### Resumo executivo")
            e1, e2, e3, e4, e5 = st.columns(5)
            with e1:
                render_metric_card("Status", executive.get("status"), color="green" if executive.get("status") == "success" else "yellow" if executive.get("status") in ("partial_success", "warning") else "red" if executive.get("status") == "failed" else "purple")
            with e2:
                render_metric_card("Tempo", _fmt_duration(executive.get("duration_seconds")), color="blue")
            with e3:
                render_metric_card("Sucesso", executive.get("success_steps", "-"), color="green")
            with e4:
                render_metric_card("Erros", executive.get("failed_steps", "-"), color="red" if executive.get("failed_steps") else "green")
            with e5:
                render_metric_card("Alertas", executive.get("warning_steps", "-"), color="purple" if executive.get("warning_steps") else "green")
            msg = executive.get("final_message")
            if msg:
                if executive.get("status") == "partial_success":
                    st.warning("Execução concluída com alertas. Verifique etapas com falha parcial.")
                    st.warning(msg)
                elif executive.get("status") == "failed":
                    st.error(msg)
                elif executive.get("status") == "warning":
                    st.warning(msg)
                else:
                    st.success(msg)


        intelligence_history = executive.get("intelligence_history") or {}
        if intelligence_history:
            st.markdown("### Evolução da Inteligência")
            trend = intelligence_history.get("trend")
            color = "green" if trend == "improving" else "red" if trend == "worsening" else "yellow"
            ev1, ev2, ev3, ev4 = st.columns(4)
            with ev1:
                render_metric_card("Score atual", intelligence_history.get("current_score", executive.get("global_intelligence_score", {}).get("score", "-")), color=color)
            with ev2:
                render_metric_card("Score anterior", intelligence_history.get("previous_score", "-"), color="blue")
            with ev3:
                delta = intelligence_history.get("score_delta")
                delta_label = "-" if delta is None else f"{float(delta):+.1f}"
                render_metric_card("Delta", delta_label, color=color)
            with ev4:
                render_metric_card("Tendência", trend or "-", color=color)

            if intelligence_history.get("summary"):
                if trend == "improving":
                    st.success(intelligence_history["summary"])
                elif trend == "worsening":
                    st.error(intelligence_history["summary"])
                else:
                    st.warning(intelligence_history["summary"])


        with st.expander("Resumo final", expanded=True):
            st.json(executive)

        steps = [dict(s) for s in get_orchestrator_steps(int(selected))]
        if steps:
            st.markdown("### Etapas")
            step_table = pd.DataFrame(
                [
                    {
                        "step": s.get("step_name"),
                        "status": s.get("status"),
                        "duration_seconds": s.get("duration_seconds"),
                        "error": s.get("error_message"),
                    }
                    for s in steps
                ]
            )
            st.dataframe(step_table, use_container_width=True, hide_index=True)

            for s in steps:
                with st.expander(f"{s.get('step_name')} · {s.get('status')}"):
                    st.markdown("**Resumo**")
                    st.json(_safe_json(s.get("summary_json")))
                    if s.get("stdout_tail"):
                        st.markdown("**stdout_tail**")
                        st.code(s.get("stdout_tail"), language="text")
                    if s.get("stderr_tail"):
                        st.markdown("**stderr_tail**")
                        st.code(s.get("stderr_tail"), language="text")
                    if s.get("error_message"):
                        st.markdown("**Erro**")
                        st.code(s.get("error_message"), language="text")

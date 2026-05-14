
from __future__ import annotations

from db import pg_compat as dbcompat

import pandas as pd
import streamlit as st

from services.automation_service import (
    MAX_AUTOMATIONS_PER_CYCLE,
    automation_summary,
    create_default_rules,
    disable_rule,
    enable_rule,
    evaluate_rules,
    list_automation_runs,
    list_rules,
    run_rule,
    update_rule_safety,
    update_rule_schedule,
)
from services.ui_helpers import ROOT_DIR
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · Automações", layout="wide")
inject_global_css()

st.title("Automações")
st.caption("Central de automações inteligentes com segurança pré-automação.")
st.info(
    "Neste patch, nenhuma automação executa sozinha. O sistema apenas sugere, prioriza, bloqueia quando necessário e exige confirmação manual."
)

if not ROOT_DIR.exists():
    st.error(f"Banco não encontrado: {ROOT_DIR}")
    st.stop()


def _connect() -> dbcompat.Connection:
    conn = dbcompat.connect(ROOT_DIR, timeout=30, check_same_thread=False)
    conn.row_factory = dbcompat.Row
    return conn


def _severity_color(value: str | None) -> str:
    if value == "critical":
        return "red"
    if value == "warning":
        return "yellow"
    return "blue"


def _bool_badge(value: bool, true_label: str, false_label: str) -> str:
    return f"🟢 {true_label}" if value else f"⚪ {false_label}"


with _connect() as conn:
    create_default_rules(conn)
    summary = automation_summary(conn)
    rules = list_rules(conn)
    suggestions = evaluate_rules(conn)
    runs = list_automation_runs(conn, 50)

render_section_header("Resumo de Segurança")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    render_metric_card("Executáveis agora", len([s for s in suggestions if s.get("selected_for_cycle")]), color="green")
with c2:
    render_metric_card("Bloqueadas", summary.get("blocked_suggestions", 0), color="red" if summary.get("blocked_suggestions") else "green")
with c3:
    render_metric_card("Cooldown", summary.get("cooldown_suggestions", 0), color="yellow" if summary.get("cooldown_suggestions") else "green")
with c4:
    render_metric_card("Próximo ciclo", summary.get("waiting_next_cycle", 0), color="purple")
with c5:
    render_metric_card("Críticas", summary.get("critical_suggestions", 0), color="red" if summary.get("critical_suggestions") else "green")
with c6:
    render_metric_card("Limite ciclo", MAX_AUTOMATIONS_PER_CYCLE, color="blue")

urgent = summary.get("most_urgent")
if urgent:
    st.caption(f"Regra mais urgente: {urgent.get('name')} · severidade={urgent.get('severity')} · confiança={urgent.get('confidence_score')}")

render_section_header("Automações selecionadas para este ciclo")
selected = [s for s in suggestions if s.get("selected_for_cycle")]
if not selected:
    st.success("Nenhuma automação selecionada para execução neste ciclo.")
else:
    for item in selected:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                st.markdown(f"**{item.get('name')}** · prioridade {item.get('priority')} · confiança {item.get('confidence_score'):.0f}%")
                st.warning(item.get("reason")) if item.get("severity") in ("warning", "critical") else st.info(item.get("reason"))
                st.caption(f"Ação recomendada: {item.get('action')}")
                st.caption(f"Dependências: {', '.join(item.get('dependencies') or []) or 'nenhuma'}")
            with right:
                st.metric("Severidade", item.get("severity"))
                if st.button("Executar", key=f"run_selected_{item.get('rule_id')}", use_container_width=True):
                    st.session_state[f"confirm_rule_{item.get('rule_id')}"] = True
                    st.rerun()

render_section_header("Sugestões do FinanceOS")
tabs = st.tabs(["Executáveis", "Bloqueadas", "Cooldown", "Próximo ciclo", "Todas"])

tab_data = [
    [s for s in suggestions if s.get("selected_for_cycle")],
    [s for s in suggestions if s.get("blocked") and not s.get("cooldown_active")],
    [s for s in suggestions if s.get("cooldown_active")],
    [s for s in suggestions if s.get("waiting_next_cycle")],
    suggestions,
]

for tab, data in zip(tabs, tab_data):
    with tab:
        if not data:
            st.info("Nenhum item nesta categoria.")
        for item in data:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    render_metric_card("Severidade", item.get("severity"), color=_severity_color(item.get("severity")))
                with c2:
                    render_metric_card("Prioridade", item.get("priority"), color="blue")
                with c3:
                    render_metric_card("Confiança", f"{float(item.get('confidence_score') or 0):.0f}%", color="purple")
                with c4:
                    status_label = "Bloqueada" if item.get("blocked") else "Selecionada" if item.get("selected_for_cycle") else "Próximo ciclo" if item.get("waiting_next_cycle") else "Info"
                    render_metric_card("Status ciclo", status_label, color="red" if item.get("blocked") else "green" if item.get("selected_for_cycle") else "yellow")

                st.markdown(f"**{item.get('name')}**")
                st.write(item.get("reason"))
                st.caption(f"Ação: {item.get('action')}")
                st.caption(f"Dependências: {', '.join(item.get('dependencies') or []) or 'nenhuma'}")
                if item.get("cooldown_active"):
                    st.warning(f"Regra em cooldown. Próxima sugestão disponível em {item.get('cooldown_remaining_minutes')} minuto(s).")
                if item.get("outside_execution_window"):
                    st.warning("Fora da janela recomendada de execução.")
                if item.get("blocked_reason"):
                    st.error(f"Bloqueada: {item.get('blocked_reason')}")

render_section_header("Regras de Automação")

for rule in rules:
    with st.container(border=True):
        rule_id = int(rule["id"])
        enabled = bool(rule.get("enabled"))
        safe_auto = bool(rule.get("safe_auto_enabled"))
        requires_confirmation = bool(rule.get("requires_confirmation"))
        dependencies = rule.get("dependencies_json") or "[]"

        st.subheader(f"{rule.get('name')} · {'🟢 Ativa' if enabled else '🔴 Desativada'}")
        st.write(rule.get("description") or "-")

        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            render_metric_card("Tipo", rule.get("rule_type"), color="blue")
        with r2:
            render_metric_card("Prioridade", rule.get("priority"), color="purple")
        with r3:
            render_metric_card("Modo seguro", "SIM" if safe_auto else "NÃO", color="green" if safe_auto else "yellow")
        with r4:
            render_metric_card("Confirmação", "SIM" if requires_confirmation else "NÃO", color="yellow" if requires_confirmation else "green")
        with r5:
            render_metric_card("Cooldown", f"{rule.get('cooldown_minutes') or 0} min", color="blue")

        st.caption(f"Grupo: {rule.get('automation_group') or '-'}")
        st.caption(f"Janela: {rule.get('execution_window_start') or '-'} até {rule.get('execution_window_end') or '-'}")
        st.caption(f"Dependências: {dependencies}")
        if rule.get("last_blocked_reason"):
            st.warning(f"Último bloqueio: {rule.get('last_blocked_reason')}")

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            if enabled:
                if st.button("Desativar", key=f"disable_{rule_id}", use_container_width=True):
                    with _connect() as conn:
                        disable_rule(conn, rule_id)
                    st.rerun()
            else:
                if st.button("Ativar", key=f"enable_{rule_id}", use_container_width=True):
                    with _connect() as conn:
                        enable_rule(conn, rule_id)
                    st.rerun()

        with a2:
            freq = st.selectbox(
                "Frequência",
                ["manual", "daily", "weekly", "smart"],
                index=["manual", "daily", "weekly", "smart"].index(rule.get("frequency") or "manual"),
                key=f"freq_{rule_id}",
            )
            if st.button("Salvar frequência", key=f"save_freq_{rule_id}", use_container_width=True):
                with _connect() as conn:
                    update_rule_schedule(conn, rule_id, freq)
                st.rerun()

        with a3:
            cooldown = st.number_input("Cooldown min", min_value=0, max_value=1440, value=int(rule.get("cooldown_minutes") or 0), step=15, key=f"cool_{rule_id}")
            if st.button("Salvar segurança", key=f"save_safety_{rule_id}", use_container_width=True):
                with _connect() as conn:
                    try:
                        update_rule_safety(
                            conn,
                            rule_id,
                            safe_auto_enabled=safe_auto,
                            requires_confirmation=requires_confirmation,
                            cooldown_minutes=int(cooldown),
                            window_start=rule.get("execution_window_start") or "",
                            window_end=rule.get("execution_window_end") or "",
                        )
                        st.success("Segurança atualizada.")
                    except Exception as exc:
                        st.error(str(exc))
                st.rerun()

        with a4:
            confirm_key = f"confirm_execute_{rule_id}"
            force_window_key = f"force_window_{rule_id}"
            ignore_cooldown_key = f"ignore_cooldown_{rule_id}"

            if requires_confirmation:
                st.checkbox("Confirmo execução", key=confirm_key)
            else:
                st.session_state[confirm_key] = True

            st.checkbox("Ignorar cooldown", key=ignore_cooldown_key)
            st.checkbox("Forçar fora da janela", key=force_window_key)

            if st.button("Executar agora", key=f"run_{rule_id}", use_container_width=True, disabled=not enabled):
                if requires_confirmation and not st.session_state.get(confirm_key):
                    st.warning("Essa regra exige confirmação antes de executar.")
                else:
                    with _connect() as conn:
                        result = run_rule(
                            conn,
                            rule_id,
                            triggered_by="manual",
                            force_outside_window=bool(st.session_state.get(force_window_key)),
                            ignore_cooldown=bool(st.session_state.get(ignore_cooldown_key)),
                        )
                    if result.get("status") == "success":
                        st.success(f"Automação criada com sucesso. Job #{result.get('job_id') or '-'}")
                    elif result.get("status") == "skipped":
                        st.warning(result.get("error"))
                    else:
                        st.error(result.get("error"))
                    st.rerun()

render_section_header("Histórico de Execuções")
if not runs:
    st.info("Nenhuma automação executada ainda.")
else:
    df = pd.DataFrame(runs)
    cols = [
        "id", "rule_name", "rule_type", "status", "triggered_by",
        "job_id", "severity", "priority", "confidence_score", "skipped_reason",
        "started_at", "finished_at", "duration_seconds", "error_message",
    ]
    show_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

with st.expander("Tabela completa de regras"):
    st.dataframe(pd.DataFrame(rules), use_container_width=True, hide_index=True)

render_section_header("Links úteis")
l1, l2, l3 = st.columns(3)
with l1:
    st.page_link("legacy_streamlit/pages/12_Jobs_e_Execucoes.py", label="Jobs e Execuções", icon="🧵")
with l2:
    st.page_link("legacy_streamlit/pages/13_Orquestrador_Geral.py", label="Orquestrador Geral", icon="🚀")
with l3:
    st.page_link("legacy_streamlit/pages/8_Saude_do_Sistema.py", label="Saúde do Sistema", icon="🩺")

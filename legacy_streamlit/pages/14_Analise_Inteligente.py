
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from services.agents.agent_manager import collect_context, run_all_agents
from services.financeos_orchestrator import bootstrap as bootstrap_orchestrator
from services.financeos_orchestrator import get_recent_orchestrator_runs
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · Análise Inteligente", layout="wide")
inject_global_css()
bootstrap_orchestrator()

st.title("Análise Inteligente")
st.caption("Camada coordenada de agentes: score global, insights priorizados e explicação final.")
st.info("Os agentes apenas analisam e explicam. Eles não executam trades, não alteram estratégias e não modificam a lógica do sistema.")


def _safe_json(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return raw or {}


def _color_by_label(label: str | None) -> str:
    if label in {"Excelente", "Bom"}:
        return "green"
    if label == "Atenção":
        return "yellow"
    if label == "Crítico":
        return "red"
    return "blue"


def _color_by_priority(priority: str | None) -> str:
    if priority == "high":
        return "red"
    if priority == "medium":
        return "yellow"
    return "green"


def _color_by_trend(trend: str | None) -> str:
    if trend == "improving":
        return "green"
    if trend == "worsening":
        return "red"
    if trend in {"stable", "first_run"}:
        return "yellow"
    return "blue"


def _render_insight(item: dict[str, Any]) -> None:
    priority = item.get("priority") or "medium"
    title = item.get("title") or "Insight"
    agent = item.get("agent") or "-"
    message = item.get("message") or ""
    recommendation = item.get("recommendation") or ""
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1:
            render_metric_card("Prioridade", priority, color=_color_by_priority(priority))
        with c2:
            st.markdown(f"**{title}** · `{agent}`")
            if message:
                st.write(message)
            if recommendation:
                st.caption(f"Recomendação: {recommendation}")


def _render_agent_expander(title: str, result: dict[str, Any]) -> None:
    with st.expander(title, expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            render_metric_card("Status", result.get("status", "-"), color="green" if result.get("status") == "ok" else "red" if result.get("status") == "critical" else "yellow")
        with c2:
            render_metric_card("Score", result.get("score", "-"), color="blue")
        with c3:
            render_metric_card("Modo", result.get("mode", "-"), color="purple")
        st.write(result.get("summary") or "-")
        if result.get("insights"):
            st.markdown("**Insights**")
            for item in result["insights"]:
                if isinstance(item, dict):
                    st.write(f"- **{item.get('priority', 'medium')}** · {item.get('title')}: {item.get('message')}")
        if result.get("recommendations"):
            st.markdown("**Recomendações**")
            for rec in result["recommendations"]:
                st.write(f"- {rec}")
        st.markdown("**Métricas usadas**")
        st.json(result.get("metrics_used") or {})
        with st.expander("JSON completo"):
            st.json(result)


def _latest_agents_from_orchestrator() -> dict[str, Any] | None:
    runs = [dict(r) for r in get_recent_orchestrator_runs(10)]
    for run in runs:
        payload = _safe_json(run.get("result_json"))
        if isinstance(payload, dict):
            agents = payload.get("agents")
            if isinstance(agents, dict):
                # Garante compatibilidade com PATCH 32 mesmo que campos estejam no nível raiz.
                if payload.get("global_intelligence_score"):
                    agents.setdefault("global_intelligence_score", payload.get("global_intelligence_score"))
                if payload.get("top_insights"):
                    agents.setdefault("top_insights", payload.get("top_insights"))
                if payload.get("warnings"):
                    agents.setdefault("warnings", payload.get("warnings"))
                if payload.get("opportunities"):
                    agents.setdefault("opportunities", payload.get("opportunities"))
                if payload.get("final_explanation"):
                    agents.setdefault("final_explanation", payload.get("final_explanation"))
                return agents
    return None


agents_result = _latest_agents_from_orchestrator()
manual_run = st.button("Rodar Análise Inteligente agora", use_container_width=True, type="primary")

if manual_run or not agents_result:
    with st.spinner("Executando pipeline coordenado de agentes..."):
        agents_result = run_all_agents(collect_context())

if not agents_result:
    st.warning("Não foi possível gerar análise inteligente.")
    st.stop()

score_payload = agents_result.get("global_intelligence_score") or (agents_result.get("aggregate") or {}).get("global_intelligence_score") or {}
top_insights = agents_result.get("top_insights") or (agents_result.get("aggregate") or {}).get("top_insights") or []
warnings = agents_result.get("warnings") or (agents_result.get("aggregate") or {}).get("warnings") or []
opportunities = agents_result.get("opportunities") or (agents_result.get("aggregate") or {}).get("opportunities") or []
final_explanation = agents_result.get("final_explanation") or (agents_result.get("explainer") or {}).get("final_explanation") or (agents_result.get("explainer") or {}).get("summary")
intelligence_history = agents_result.get("intelligence_history") or {}

render_section_header("Score Global de Inteligência")
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    render_metric_card("Score Global", score_payload.get("score", "-"), color=_color_by_label(score_payload.get("label")))
with c2:
    render_metric_card("Classificação", score_payload.get("label", "-"), color=_color_by_label(score_payload.get("label")))
with c3:
    if final_explanation:
        st.success(final_explanation) if score_payload.get("label") in {"Excelente", "Bom"} else st.warning(final_explanation)

with st.expander("Drivers e penalidades do score"):
    st.markdown("**Drivers**")
    for item in score_payload.get("drivers") or []:
        st.write(f"- {item}")
    st.markdown("**Penalidades**")
    for item in score_payload.get("penalties") or []:
        st.write(f"- {item}")

render_section_header("Evolução da Inteligência")
if intelligence_history:
    trend = intelligence_history.get("trend")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        render_metric_card("Score atual", intelligence_history.get("current_score", score_payload.get("score", "-")), color=_color_by_trend(trend))
    with h2:
        render_metric_card("Score anterior", intelligence_history.get("previous_score", "-"), color="blue")
    with h3:
        delta = intelligence_history.get("score_delta")
        delta_label = "-" if delta is None else f"{delta:+.1f}"
        render_metric_card("Delta", delta_label, color=_color_by_trend(trend))
    with h4:
        render_metric_card("Tendência", trend or "-", color=_color_by_trend(trend))

    summary = intelligence_history.get("summary")
    if summary:
        if trend == "improving":
            st.success(summary)
        elif trend == "worsening":
            st.error(summary)
        else:
            st.warning(summary)

    c_imp, c_wor = st.columns(2)
    with c_imp:
        st.markdown("**Áreas que melhoraram**")
        improved = intelligence_history.get("improved_areas") or []
        if improved:
            for item in improved:
                st.write(f"- {item}")
        else:
            st.caption("Nenhuma melhora clara identificada.")
    with c_wor:
        st.markdown("**Áreas que pioraram**")
        worsened = intelligence_history.get("worsened_areas") or []
        if worsened:
            for item in worsened:
                st.write(f"- {item}")
        else:
            st.caption("Nenhuma piora clara identificada.")
else:
    st.info("Primeira execução inteligente registrada ou histórico ainda indisponível.")

render_section_header("Top Insights · Alta prioridade")
if top_insights:
    for item in top_insights:
        _render_insight(item)
else:
    st.success("Nenhum insight de alta prioridade encontrado.")

render_section_header("Alertas · Média prioridade")
if warnings:
    for item in warnings:
        _render_insight(item)
else:
    st.success("Nenhum alerta médio encontrado.")

render_section_header("Oportunidades · Baixa prioridade")
if opportunities:
    for item in opportunities:
        _render_insight(item)
else:
    st.info("Nenhuma oportunidade incremental registrada.")

render_section_header("Análise por Agente")
_render_agent_expander("Agent Catalog · Catálogo", agents_result.get("catalog") or {})
_render_agent_expander("Agent Strategy · Estratégia", agents_result.get("strategy") or {})
_render_agent_expander("Agent Risk · Risco", agents_result.get("risk") or {})
_render_agent_expander("Agent Analyst · Visão geral coordenada", agents_result.get("analyst") or {})
_render_agent_expander("Agent Explainer · Explicação final", agents_result.get("explainer") or {})

with st.expander("Payload consolidado dos agentes"):
    st.json(agents_result)

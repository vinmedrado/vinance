import json
from db import pg_compat as dbcompat

import pandas as pd
import streamlit as st

from services.ui_helpers import ROOT_DIR, format_number, format_percent, safe_count, safe_query, table_exists
from services.strategy_comparator import load_backtest_metrics, rank_backtests
from services.strategy_interpreter import calculate_strategy_score
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_strategy_card

from services.auth_middleware import check_auth
user = check_auth()
st.set_page_config(page_title="FinanceOS · Visão Geral", layout="wide")
inject_global_css()
render_hero(
    "FinanceOS",
    "Quantitative Wealth Intelligence",
    eyebrow="Visão Geral Executiva",
    status="Painel operacional com dados, estratégias e saúde do sistema",
)

if not ROOT_DIR.exists():
    st.error(f"Banco não encontrado: {ROOT_DIR}")
    st.stop()

with dbcompat.connect(ROOT_DIR) as conn:
    conn.row_factory = dbcompat.Row
    total_assets = safe_count(conn, "assets")
    price_rows = safe_count(conn, "asset_prices")
    total_scores = safe_count(conn, "asset_scores")
    total_backtests = safe_count(conn, "backtest_runs")
    assets_with_price = 0
    if table_exists(conn, "asset_prices"):
        assets_with_price = conn.execute("SELECT COUNT(DISTINCT asset_id) FROM asset_prices WHERE asset_id IS NOT NULL").fetchone()[0]
    assets_without_price = max(total_assets - assets_with_price, 0)
    all_backtests = load_backtest_metrics(conn)

ranked = rank_backtests(all_backtests)
best_overall = ranked[0] if ranked else None
last_bt = safe_query("""
SELECT br.id, br.strategy_name AS strategy, br.asset_class, br.status, br.created_at,
       bm.total_return, bm.max_drawdown, bm.sharpe_ratio, bm.turnover, bm.total_trades
FROM backtest_runs br
LEFT JOIN backtest_metrics bm ON bm.backtest_id = br.id
ORDER BY br.id DESC LIMIT 1
""")


if best_overall:
    render_hero(
        "Melhor estratégia atual",
        f"{best_overall.get('strategy') or best_overall.get('strategy_name') or 'Estratégia'} · Top N {best_overall.get('top_n', '-')}",
        eyebrow="Destaque do sistema",
        status=f"Retorno {format_percent(best_overall.get('total_return'))} | Sharpe {float(best_overall.get('sharpe_ratio') or 0):.2f} | DD {format_percent(best_overall.get('max_drawdown'))}",
        metrics={
            "Score": f"{int(best_overall.get('comparison_score') or calculate_strategy_score(best_overall))}/100",
            "Turnover": f"{float(best_overall.get('turnover') or 0):.2f}",
            "Trades": format_number(best_overall.get('total_trades'), 0),
        },
    )

st.markdown("### Status geral")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_metric_card("Ativos cadastrados", format_number(total_assets), "Catálogo total", "blue")
with c2:
    render_metric_card("Ativos com histórico", format_number(assets_with_price), "Com pelo menos um preço", "green")
with c3:
    color = "red" if assets_without_price else "green"
    render_metric_card("Ativos sem dados", format_number(assets_without_price), "Precisam de sincronização", color)
with c4:
    render_metric_card("Registros de preço", format_number(price_rows), "Base histórica", "default")

c5, c6, c7, c8 = st.columns(4)
with c5:
    render_metric_card("Scores calculados", format_number(total_scores), "Analysis Engine", "blue")
with c6:
    render_metric_card("Estratégias testadas", format_number(total_backtests), "Backtests salvos", "default")
with c7:
    score_avg = 0
    if ranked:
        score_avg = sum(int(x.get("comparison_score") or calculate_strategy_score(x)) for x in ranked) / max(len(ranked), 1)
    render_metric_card("Score médio", f"{score_avg:.0f}/100", "Entre backtests", "yellow" if score_avg < 60 else "green")
with c8:
    status = str(last_bt.iloc[0]["status"]) if not last_bt.empty else "Sem backtests"
    render_metric_card("Status geral", status, "Última execução", "green" if status.lower() in {"success", "completed", "ok"} else "yellow")

st.markdown("---")
st.markdown("### Melhor estratégia atual")
if best_overall:
    render_strategy_card(best_overall, rank=1, highlight=True)
else:
    st.info("Ainda não há backtests suficientes para definir a melhor estratégia.")

st.markdown("---")
left, right = st.columns([1, 1.15])
with left:
    st.markdown("### Ativos por classe")
    df_class = safe_query("SELECT COALESCE(asset_class, 'unknown') AS asset_class, COUNT(*) AS total FROM assets GROUP BY asset_class ORDER BY total DESC")
    if df_class.empty:
        st.info("Sem ativos cadastrados.")
    else:
        st.bar_chart(df_class.set_index("asset_class"))
        with st.expander("Ver tabela detalhada"):
            st.dataframe(df_class, use_container_width=True, hide_index=True)

with right:
    st.markdown("### Últimos backtests")
    latest = safe_query("""
    SELECT br.id, br.strategy_name AS strategy, br.asset_class, br.status, br.created_at,
           bm.total_return, bm.max_drawdown, bm.sharpe_ratio, bm.turnover, bm.total_trades
    FROM backtest_runs br
    LEFT JOIN backtest_metrics bm ON bm.backtest_id = br.id
    ORDER BY br.id DESC LIMIT 8
    """)
    if latest.empty:
        st.info("Nenhum backtest encontrado.")
    else:
        for _, row in latest.head(4).iterrows():
            data = row.to_dict()
            data["comparison_score"] = calculate_strategy_score(data)
            render_strategy_card(data, rank=None, highlight=False)
        with st.expander("Ver todos os últimos backtests"):
            st.dataframe(latest, use_container_width=True, hide_index=True)


# PATCH 30 — Orquestrador Geral
render_section_header("Orquestrador Geral")
try:
    from services.financeos_orchestrator import bootstrap as _orch_bootstrap, get_recent_orchestrator_runs
    _orch_bootstrap()
    _runs = [dict(r) for r in get_recent_orchestrator_runs(1)]
    if _runs:
        _last = _runs[0]
        _status = _last.get("status")
        _duration = _last.get("duration_seconds") or "-"
        c_orch1, c_orch2, c_orch3 = st.columns(3)
        with c_orch1:
            render_metric_card("Última execução", f"#{_last.get('id')}", color="blue")
        with c_orch2:
            render_metric_card("Status", _status, color="green" if _status == "success" else "red" if _status == "failed" else "purple")
        with c_orch3:
            render_metric_card("Duração", _duration, color="blue")
        if _status not in ("success", None):
            st.warning("Última execução do orquestrador não finalizou 100% com sucesso. Veja detalhes na página Orquestrador Geral.")
    else:
        st.info("Nenhuma execução do orquestrador registrada ainda.")
    st.page_link("legacy_streamlit/pages/13_Orquestrador_Geral.py", label="Abrir Orquestrador Geral", icon="🚀")
except Exception as exc:
    st.warning(f"Não foi possível carregar resumo do orquestrador: {exc}")


# PATCH 33 — Evolução da Inteligência
render_section_header("Evolução da Inteligência")
try:
    from services.financeos_orchestrator import bootstrap as _orch_bootstrap, get_recent_orchestrator_runs
    _orch_bootstrap()
    _runs = [dict(r) for r in get_recent_orchestrator_runs(1)]
    if _runs:
        _payload = {}
        try:
            _payload = json.loads(_runs[0].get("result_json") or "{}")
        except Exception:
            _payload = {}
        _score = (_payload.get("global_intelligence_score") or {}).get("score")
        _label = (_payload.get("global_intelligence_score") or {}).get("label")
        _hist = _payload.get("intelligence_history") or {}
        _trend = _hist.get("trend")
        _delta = _hist.get("score_delta")
        _delta_label = "-" if _delta is None else f"{float(_delta):+.1f}"

        _color = "green" if _trend == "improving" else "red" if _trend == "worsening" else "yellow"
        c_ai1, c_ai2, c_ai3 = st.columns(3)
        with c_ai1:
            render_metric_card("Score Inteligente", _score if _score is not None else "-", color=_color)
        with c_ai2:
            render_metric_card("Classificação", _label or "-", color=_color)
        with c_ai3:
            render_metric_card("Delta vs anterior", _delta_label, color=_color)
        if _hist.get("summary"):
            st.info(_hist["summary"])
    else:
        st.info("Nenhuma execução inteligente registrada ainda.")
    st.page_link("legacy_streamlit/pages/14_Analise_Inteligente.py", label="Abrir Análise Inteligente", icon="🧠")
except Exception as exc:
    st.warning(f"Não foi possível carregar evolução inteligente: {exc}")


# PATCH 34 — BI da Inteligência
render_section_header("BI da Inteligência")
try:
    from db import pg_compat as dbcompat
    from services.intelligence_bi_service import load_intelligence_history, build_intelligence_dataframe, calculate_bi_kpis
    with dbcompat.connect(ROOT_DIR) as _conn:
        _runs_bi = load_intelligence_history(_conn)
    _df_bi = build_intelligence_dataframe(_runs_bi)
    if _df_bi.empty:
        st.info("Ainda não há histórico inteligente suficiente para o BI.")
    else:
        _kpis_bi = calculate_bi_kpis(_df_bi)
        _trend_bi = _kpis_bi.get("current_trend")
        _color_bi = "green" if _trend_bi == "improving" else "red" if _trend_bi == "worsening" else "yellow"
        _delta = _kpis_bi.get("last_delta")
        _delta_label = "-" if _delta is None else f"{float(_delta):+.1f}"
        bi1, bi2, bi3 = st.columns(3)
        with bi1:
            render_metric_card("Score Global Atual", _kpis_bi.get("last_score") or "-", color=_color_bi)
        with bi2:
            render_metric_card("Tendência", _trend_bi or "-", color=_color_bi)
        with bi3:
            render_metric_card("Delta", _delta_label, color=_color_bi)
    st.page_link("legacy_streamlit/pages/15_BI_Inteligencia.py", label="Abrir BI da Inteligência", icon="📊")
except Exception as exc:
    st.warning(f"Não foi possível carregar BI da Inteligência: {exc}")


# PATCH 35 — Automações Inteligentes
render_section_header("Automações Inteligentes")
try:
    from services.automation_service import create_default_rules, automation_summary
    with dbcompat.connect(ROOT_DIR) as _auto_conn:
        create_default_rules(_auto_conn)
        _auto_summary = automation_summary(_auto_conn)

    a1, a2, a3 = st.columns(3)
    with a1:
        render_metric_card("Regras ativas", _auto_summary.get("active_rules", 0), color="green")
    with a2:
        render_metric_card("Sugestões pendentes", _auto_summary.get("pending_suggestions", 0), color="yellow" if _auto_summary.get("pending_suggestions") else "green")
    with a3:
        _last = _auto_summary.get("last_run") or {}
        render_metric_card("Último job automático", _last.get("job_id") or "-", color="blue")
    st.page_link("legacy_streamlit/pages/16_Automacoes.py", label="Abrir Automações", icon="⚙️")
except Exception as exc:
    st.warning(f"Não foi possível carregar automações inteligentes: {exc}")

try:
    from services.automation_service import evaluate_rules
    from db import pg_compat as dbcompat
    with dbcompat.connect(ROOT_DIR) as conn:
        _sugs = evaluate_rules(conn)
    critical = len([s for s in _sugs if s.get("severity")=="critical"])
    warning = len([s for s in _sugs if s.get("severity")=="warning"])
    st.markdown(f"**Sugestões críticas:** {critical} | warnings: {warning}")
except:
    pass


# PATCH 35.2 — Segurança Pré-Automação
render_section_header("Segurança das Automações")
try:
    from services.automation_service import automation_summary, create_default_rules
    with dbcompat.connect(ROOT_DIR) as _auto_conn:
        create_default_rules(_auto_conn)
        _safe_summary = automation_summary(_auto_conn)

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        render_metric_card("Críticas", _safe_summary.get("critical_suggestions", 0), color="red" if _safe_summary.get("critical_suggestions") else "green")
    with s2:
        render_metric_card("Warnings", _safe_summary.get("warning_suggestions", 0), color="yellow" if _safe_summary.get("warning_suggestions") else "green")
    with s3:
        render_metric_card("Em cooldown", _safe_summary.get("cooldown_suggestions", 0), color="yellow" if _safe_summary.get("cooldown_suggestions") else "green")
    with s4:
        render_metric_card("Bloqueadas", _safe_summary.get("blocked_suggestions", 0), color="red" if _safe_summary.get("blocked_suggestions") else "green")

    _urgent = _safe_summary.get("most_urgent")
    if _urgent:
        st.caption(f"Regra mais urgente: {_urgent.get('name')} · prioridade {_urgent.get('priority')} · severidade {_urgent.get('severity')}")
    st.page_link("legacy_streamlit/pages/16_Automacoes.py", label="Abrir Automações", icon="⚙️")
except Exception as exc:
    st.warning(f"Não foi possível carregar segurança das automações: {exc}")


# PATCH 36 — Machine Learning
render_section_header("Machine Learning")
try:
    from services.ml_common import connect as _ml_connect, bootstrap_ml_tables
    from services.ml_model_registry import ml_overview
    with _ml_connect() as _ml_conn:
        bootstrap_ml_tables(_ml_conn)
    _ml_overview = ml_overview()
    ml1, ml2, ml3 = st.columns(3)
    with ml1:
        render_metric_card("Datasets ML", _ml_overview.get("datasets", 0), color="blue")
    with ml2:
        render_metric_card("Modelos ML", _ml_overview.get("models", 0), color="purple")
    with ml3:
        render_metric_card("Previsões ML", _ml_overview.get("predictions", 0), color="green")
    st.page_link("legacy_streamlit/pages/17_Machine_Learning.py", label="Abrir Machine Learning", icon="🤖")
except Exception as exc:
    st.warning(f"Não foi possível carregar resumo de ML: {exc}")

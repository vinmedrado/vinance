from __future__ import annotations

from db import pg_compat as dbcompat

import pandas as pd
import streamlit as st

from services.ui_components import inject_global_css, render_metric_card, render_section_header
from services.ui_helpers import ROOT_DIR, format_number, safe_count, table_exists
from services.asset_quality_service import ensure_asset_quality_columns
from services.catalog_pipeline_runs import ensure_catalog_pipeline_runs_table
from services.market_data_pipeline_runs import ensure_market_data_pipeline_runs_table

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · Saúde do Sistema", layout="wide")
inject_global_css()
st.title("Saúde do Sistema")
st.caption("Leitura operacional do banco e das tabelas principais. Não altera dados.")

c1, c2, c3 = st.columns(3)
with c1: render_metric_card("Caminho do banco", str(ROOT_DIR), color="blue")
with c2: render_metric_card("Existe", "SIM" if ROOT_DIR.exists() else "NÃO", color="green" if ROOT_DIR.exists() else "red")
with c3: render_metric_card("Tamanho", f"{ROOT_DIR.stat().st_size / (1024*1024):.2f} MB" if ROOT_DIR.exists() else "-", color="purple")

if not ROOT_DIR.exists():
    st.error("Banco não encontrado.")
    st.stop()

tables_main = [
    "asset_catalog",
    "assets",
    "asset_prices",
    "asset_dividends",
    "dividends",
    "market_indices",
    "macro_indicators",
    "asset_analysis_metrics",
    "asset_scores",
    "backtest_runs",
    "backtest_metrics",
    "backtest_trades",
    "backtest_equity_curve",
    "optimization_runs",
    "optimization_results",
    "catalog_pipeline_runs",
    "market_data_pipeline_runs",
]

alerts = []
with dbcompat.connect(ROOT_DIR) as conn:
    conn.row_factory = dbcompat.Row
    ensure_catalog_pipeline_runs_table(conn)
    ensure_market_data_pipeline_runs_table(conn)
    existing = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)

    if table_exists(conn, "asset_catalog"):
        ensure_asset_quality_columns(conn)
        total_catalog = safe_count(conn, "asset_catalog")
        active = safe_count(conn, "asset_catalog", "api_status='active'")
        pending = safe_count(conn, "asset_catalog", "api_status='pending_validation'")
        stale = safe_count(conn, "asset_catalog", "api_status='stale'")
        not_found = safe_count(conn, "asset_catalog", "api_status='not_found'")
        errors = safe_count(conn, "asset_catalog", "api_status='error'")
        recommended = safe_count(conn, "asset_catalog", "recommendation_tag='recommended'")
        weak_data = safe_count(conn, "asset_catalog", "api_status='weak_data' OR reliability_status='weak_data'")
        invalid = safe_count(conn, "asset_catalog", "reliability_status='invalid' OR api_status='not_found'")
        no_score = safe_count(conn, "asset_catalog", "COALESCE(data_quality_score,0)=0 OR updated_quality_at IS NULL")
        no_history = safe_count(conn, "asset_catalog", "COALESCE(price_records,0)=0")
        no_source = safe_count(conn, "asset_catalog", "COALESCE(last_source_used, preferred_source, '')=''")
        no_validated_at = safe_count(conn, "asset_catalog", "last_validated_at IS NULL")
        last_validation = conn.execute("SELECT MAX(last_validated_at) FROM asset_catalog").fetchone()[0]
        last_quality = conn.execute("SELECT MAX(updated_quality_at) FROM asset_catalog").fetchone()[0]

        st.subheader("Saúde do Catálogo")
        a, b, c, d, e = st.columns(5)
        with a: render_metric_card("Total catálogo", total_catalog, color="blue")
        with b: render_metric_card("Active", active, color="green")
        with c: render_metric_card("Recomendados", recommended, color="green")
        with d: render_metric_card("Weak data", weak_data, color="yellow")
        with e: render_metric_card("Invalid", invalid, color="red")
        f, g, h, i = st.columns(4)
        with f: render_metric_card("Sem score", no_score, color="yellow")
        with g: render_metric_card("Sem histórico", no_history, color="red")
        with h: render_metric_card("Pendentes", pending, color="yellow")
        with i: render_metric_card("Erros API", errors, color="dark_red")

        st.subheader("Estabilidade do Catálogo")
        j, k, l, m, n = st.columns(5)
        with j: render_metric_card("Stale", stale, color="yellow")
        with k: render_metric_card("Weak data", weak_data, color="yellow")
        with l: render_metric_card("Sem fonte", no_source, color="red")
        with m: render_metric_card("Sem validação", no_validated_at, color="yellow")
        with n: render_metric_card("Último pipeline", last_validation or "-", color="blue")
        st.caption(f"Última validação API: {last_validation or '-'} · Última qualidade: {last_quality or '-'}")

        if total_catalog and errors / max(total_catalog, 1) > 0.15:
            alerts.append("Muitos erros no asset_catalog. Revalidar símbolos ou revisar fontes.")
        if stale > max(20, total_catalog * 0.25):
            alerts.append(f"Muitos ativos stale no catálogo: {stale}. Rode update_catalog_pipeline com --force se necessário.")
        if weak_data > max(20, total_catalog * 0.25):
            alerts.append(f"Muitos ativos com weak_data: {weak_data}. Priorize histórico de preços.")
        if no_source > 0:
            alerts.append(f"Existem {no_source} ativos sem fonte preferencial/última fonte usada.")
        if no_validated_at > max(20, total_catalog * 0.25):
            alerts.append(f"Muitos ativos sem last_validated_at: {no_validated_at}.")
        if pending > max(20, total_catalog * 0.25):
            alerts.append(f"Muitos ativos pendentes de validação no asset_catalog: {pending}.")
        if invalid > max(10, total_catalog * 0.10):
            alerts.append(f"Muitos ativos inválidos no catálogo: {invalid}.")
        if no_history > max(20, total_catalog * 0.30):
            alerts.append(f"Muitos ativos sem histórico de preço: {no_history}. Rode sync_historical_prices e update_asset_quality_scores.")
        if no_score:
            alerts.append(f"Existem {no_score} ativos sem score de qualidade. Rode: python scripts/update_asset_quality_scores.py --limit=500")
    else:
        alerts.append("Tabela asset_catalog ainda não existe.")

    render_section_header("Automações do Catálogo")
    try:
        last_rows = pd.read_sql_query("""
            SELECT operation, status, started_at, finished_at, duration_seconds, error_message
              FROM catalog_pipeline_runs
             ORDER BY started_at DESC, id DESC
             LIMIT 20
        """, conn)
        def _last_value(operation: str, field: str = "started_at"):
            subset = last_rows[last_rows["operation"] == operation] if not last_rows.empty else pd.DataFrame()
            if subset.empty:
                return "-"
            return subset.iloc[0].get(field) or "-"

        last_pipeline = _last_value("full_pipeline")
        last_validation_run = _last_value("validate_catalog")
        last_crypto = _last_value("sync_crypto")
        last_quality_run = _last_value("update_quality")
        last_any_status = last_rows.iloc[0]["status"] if not last_rows.empty else "-"

        o1, o2, o3, o4, o5 = st.columns(5)
        with o1: render_metric_card("Último pipeline", last_pipeline, color="blue")
        with o2: render_metric_card("Última validação", last_validation_run, color="green")
        with o3: render_metric_card("Última cripto", last_crypto, color="purple")
        with o4: render_metric_card("Última qualidade", last_quality_run, color="yellow")
        with o5: render_metric_card("Status recente", last_any_status, color="green" if str(last_any_status).lower() == "success" else "red" if str(last_any_status).lower() == "error" else "yellow")

        recent_errors = last_rows[last_rows["status"].str.lower().eq("error")] if not last_rows.empty else pd.DataFrame()
        if not recent_errors.empty:
            alerts.append(f"Existem {len(recent_errors)} erro(s) recente(s) nas automações do catálogo.")
            with st.expander("Erros recentes das automações do catálogo"):
                st.dataframe(recent_errors, use_container_width=True, hide_index=True)
        else:
            st.success("Nenhum erro recente nas automações do catálogo.")
    except Exception as exc:
        alerts.append(f"Não foi possível ler catalog_pipeline_runs: {exc}")


    render_section_header("Dados de Mercado")
    try:
        market_runs = pd.read_sql_query("""
            SELECT operation, status, started_at, finished_at, duration_seconds, error_message
              FROM market_data_pipeline_runs
             WHERE parent_run_id IS NULL
             ORDER BY started_at DESC, id DESC
             LIMIT 30
        """, conn)

        def _last_market_value(operation: str, field: str = "finished_at"):
            subset = market_runs[market_runs["operation"] == operation] if not market_runs.empty else pd.DataFrame()
            if subset.empty:
                return "-"
            return subset.iloc[0].get(field) or "-"

        last_prices = _last_market_value("historical_prices")
        last_dividends = _last_market_value("dividends")
        last_indices = _last_market_value("market_indices")
        last_macro = _last_market_value("macro_indicators")
        last_full = _last_market_value("full_pipeline")
        last_status = market_runs.iloc[0]["status"] if not market_runs.empty else "-"

        md1, md2, md3, md4, md5, md6 = st.columns(6)
        with md1: render_metric_card("Última atualização de preços", last_prices, color="blue")
        with md2: render_metric_card("Última atualização de dividendos", last_dividends, color="green")
        with md3: render_metric_card("Última atualização de índices", last_indices, color="purple")
        with md4: render_metric_card("Última macro/CDI", last_macro, color="yellow")
        with md5: render_metric_card("Último pipeline completo", last_full, color="blue")
        with md6: render_metric_card("Status última execução", last_status, color="green" if str(last_status).lower() == "success" else "red" if str(last_status).lower() == "error" else "yellow")

        if market_runs.empty:
            alerts.append("Nenhuma execução de dados de mercado registrada.")
        else:
            recent_market_errors = market_runs[market_runs["status"].astype(str).str.lower().eq("error")]
            if str(last_status).lower() == "error":
                alerts.append("A última execução de dados de mercado falhou.")
            if not recent_market_errors.empty:
                alerts.append(f"Existem {len(recent_market_errors)} erro(s) recente(s) em dados de mercado.")
                with st.expander("Erros recentes de Dados de Mercado"):
                    st.dataframe(recent_market_errors, use_container_width=True, hide_index=True)
            else:
                st.success("Nenhum erro recente nas execuções de dados de mercado.")
    except Exception as exc:
        alerts.append(f"Não foi possível ler market_data_pipeline_runs: {exc}")

    asset_prices_total = safe_count(conn, "asset_prices")
    if asset_prices_total == 0:
        alerts.append("asset_prices vazio. Rode a Automação de Dados de Mercado para carregar histórico de preços.")
    if table_exists(conn, "assets") and table_exists(conn, "asset_prices"):
        try:
            assets_without_prices = conn.execute("""
                SELECT COUNT(*) FROM assets a
                LEFT JOIN asset_prices p ON p.asset_id = a.id
                WHERE p.id IS NULL
            """).fetchone()[0]
            if assets_without_prices > max(20, safe_count(conn, "assets") * 0.30):
                alerts.append(f"Há muitos ativos sem preço: {assets_without_prices}.")
        except Exception:
            pass

    render_section_header("Tabelas principais")
    rows = []
    for table in tables_main:
        exists = table_exists(conn, table)
        total = safe_count(conn, table) if exists else None
        rows.append({"table": table, "exists": exists, "rows": total})
        if not exists:
            alerts.append(f"Tabela ausente: {table}")
    health = pd.DataFrame(rows)
    st.dataframe(health, use_container_width=True, hide_index=True)

    if safe_count(conn, "assets") == 0:
        alerts.append("Tabela assets vazia.")
    if safe_count(conn, "asset_prices") == 0:
        alerts.append("Tabela asset_prices vazia.")
    if table_exists(conn, "backtest_runs"):
        try:
            old_running = conn.execute("SELECT COUNT(*) FROM backtest_runs WHERE status = 'running'").fetchone()[0]
            if old_running:
                alerts.append(f"Existem {old_running} backtests em status running.")
        except Exception:
            pass
    if table_exists(conn, "assets") and table_exists(conn, "asset_prices"):
        try:
            sem_dados = conn.execute("""
                SELECT COUNT(*) FROM assets a
                LEFT JOIN asset_prices p ON p.asset_id = a.id
                WHERE p.id IS NULL
            """).fetchone()[0]
            if sem_dados:
                alerts.append(f"Ativos sem dados de preço: {sem_dados}")
        except Exception:
            pass

with st.expander("Ver todas as tabelas existentes"):
    st.dataframe(existing, use_container_width=True, hide_index=True)

st.subheader("Alertas")
if alerts:
    for alert in alerts:
        st.warning(alert)
else:
    st.success("Nenhum alerta crítico encontrado.")


# PATCH 30 — Saúde do Orquestrador Geral
render_section_header("Orquestrador Geral")
try:
    from services.financeos_orchestrator import bootstrap as _orch_bootstrap, get_recent_orchestrator_runs
    _orch_bootstrap()
    _runs = [dict(r) for r in get_recent_orchestrator_runs(5)]
    if not _runs:
        st.warning("Nenhuma execução do orquestrador registrada.")
    else:
        _last = _runs[0]
        _status = _last.get("status")
        c_orch1, c_orch2, c_orch3 = st.columns(3)
        with c_orch1:
            render_metric_card("Última execução", f"#{_last.get('id')}", color="blue")
        with c_orch2:
            render_metric_card("Status", _status, color="green" if _status == "success" else "red" if _status == "failed" else "purple")
        with c_orch3:
            render_metric_card("Duração", _last.get("duration_seconds") or "-", color="blue")
        if _status not in ("success", None):
            st.error("Última execução do orquestrador falhou ou teve sucesso parcial.")
        st.dataframe(pd.DataFrame(_runs), use_container_width=True, hide_index=True)
    st.page_link("legacy_streamlit/pages/13_Orquestrador_Geral.py", label="Abrir Orquestrador Geral", icon="🚀")
except Exception as exc:
    st.warning(f"Não foi possível carregar saúde do orquestrador: {exc}")


# PATCH 35 — Saúde das Automações Inteligentes
render_section_header("Automações Inteligentes")
try:
    from services.automation_service import create_default_rules, automation_summary, evaluate_rules, list_rules, list_automation_runs
    with dbcompat.connect(ROOT_DIR) as _auto_conn:
        create_default_rules(_auto_conn)
        _auto_summary = automation_summary(_auto_conn)
        _auto_rules = list_rules(_auto_conn)
        _auto_suggestions = evaluate_rules(_auto_conn)
        _auto_runs = list_automation_runs(_auto_conn, 10)

    disabled_critical = [
        r for r in _auto_rules
        if not int(r.get("enabled") or 0)
        and r.get("rule_type") in ("catalog_update", "market_data_update", "orchestrator_run", "health_check")
    ]
    failed_recent = [r for r in _auto_runs if r.get("status") == "failed"]
    pending_suggestions = [s for s in _auto_suggestions if s.get("recommended")]

    au1, au2, au3 = st.columns(3)
    with au1:
        render_metric_card("Falhas recentes", len(failed_recent), color="red" if failed_recent else "green")
    with au2:
        render_metric_card("Regras críticas desativadas", len(disabled_critical), color="red" if disabled_critical else "green")
    with au3:
        render_metric_card("Sugestões pendentes", len(pending_suggestions), color="yellow" if pending_suggestions else "green")

    if failed_recent:
        st.error("Há automações com falha recente. Revise o histórico na página Automações.")
    if disabled_critical:
        st.warning("Existem regras críticas desativadas.")
    if pending_suggestions:
        with st.expander("Ver sugestões pendentes"):
            for item in pending_suggestions:
                st.write(f"- **{item.get('name')}**: {item.get('reason')}")

    st.page_link("legacy_streamlit/pages/16_Automacoes.py", label="Abrir Automações", icon="⚙️")
except Exception as exc:
    st.warning(f"Não foi possível carregar saúde das automações: {exc}")


# PATCH 35.2 — Segurança Pré-Automação
render_section_header("Segurança Pré-Automação")
try:
    from services.automation_service import automation_summary, create_default_rules, evaluate_rules, list_rules
    with dbcompat.connect(ROOT_DIR) as _auto_conn:
        create_default_rules(_auto_conn)
        _safe_summary = automation_summary(_auto_conn)
        _safe_rules = list_rules(_auto_conn)
        _safe_suggestions = evaluate_rules(_auto_conn)

    blocked = [s for s in _safe_suggestions if s.get("blocked")]
    waiting = [s for s in _safe_suggestions if s.get("waiting_next_cycle")]
    no_safe = [r for r in _safe_rules if not int(r.get("safe_auto_enabled") or 0)]
    heavy_confirmed = [
        r for r in _safe_rules
        if r.get("rule_type") in ("catalog_update", "market_data_update", "orchestrator_run")
        and int(r.get("requires_confirmation") or 0)
    ]

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        render_metric_card("Bloqueadas por regra", len(blocked), color="red" if blocked else "green")
    with p2:
        render_metric_card("Sem modo seguro", len(no_safe), color="yellow" if no_safe else "green")
    with p3:
        render_metric_card("Pesadas com confirmação", len(heavy_confirmed), color="green")
    with p4:
        render_metric_card("Próximo ciclo", len(waiting), color="purple" if waiting else "green")

    if blocked:
        with st.expander("Automações bloqueadas"):
            for item in blocked:
                st.write(f"- **{item.get('name')}**: {item.get('blocked_reason')}")
    if waiting:
        with st.expander("Aguardando próximo ciclo"):
            for item in waiting:
                st.write(f"- **{item.get('name')}**: prioridade {item.get('priority')} · confiança {item.get('confidence_score')}")

    st.page_link("legacy_streamlit/pages/16_Automacoes.py", label="Abrir Automações", icon="⚙️")
except Exception as exc:
    st.warning(f"Não foi possível carregar segurança pré-automação: {exc}")


# PATCH 36 — Saúde do Machine Learning
render_section_header("Machine Learning")
try:
    from services.ml_common import connect as _ml_connect, bootstrap_ml_tables
    from services.ml_model_registry import ml_overview
    with _ml_connect() as _ml_conn:
        bootstrap_ml_tables(_ml_conn)
    _ml_overview = ml_overview()
    mlh1, mlh2, mlh3 = st.columns(3)
    with mlh1:
        render_metric_card("Datasets", _ml_overview.get("datasets", 0), color="blue")
    with mlh2:
        render_metric_card("Modelos", _ml_overview.get("models", 0), color="purple")
    with mlh3:
        render_metric_card("Previsões", _ml_overview.get("predictions", 0), color="green")
    if _ml_overview.get("datasets", 0) == 0:
        st.info("Nenhum dataset ML criado ainda.")
    elif _ml_overview.get("models", 0) == 0:
        st.warning("Há dataset ML, mas nenhum modelo treinado.")
    st.page_link("legacy_streamlit/pages/17_Machine_Learning.py", label="Abrir Machine Learning", icon="🤖")
except Exception as exc:
    st.warning(f"Não foi possível carregar saúde de ML: {exc}")

from __future__ import annotations

from db import pg_compat as dbcompat

import pandas as pd
import streamlit as st

from services.asset_quality_service import ensure_asset_quality_columns
from services.asset_ranking_service import (
    get_assets_to_avoid,
    get_catalog_summary,
    get_recommended_assets,
    get_top_assets,
)
from services.ui_components import inject_global_css, render_metric_card, render_section_header
from services.ui_helpers import ROOT_DIR, table_exists, safe_count

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
st.set_page_config(page_title="FinanceOS · Catálogo Inteligente", layout="wide")
inject_global_css()
st.title("Catálogo Inteligente de Ativos")
st.caption("Qualidade de dados, confiabilidade e recomendação para análise/backtests.")

if not ROOT_DIR.exists():
    st.error("Banco não encontrado.")
    st.stop()


def _status_color(status: str | None) -> str:
    return {
        "excellent": "green",
        "good": "blue",
        "usable": "yellow",
        "weak_data": "red",
        "invalid": "dark_red",
        "unknown": "default",
    }.get(str(status or "unknown"), "default")


def _asset_card(asset: dict, rank: int | None = None) -> None:
    score = float(asset.get("data_quality_score") or 0)
    status = asset.get("reliability_status") or "unknown"
    tag = asset.get("recommendation_tag") or "pending"
    color = _status_color(status)
    border = {
        "green": "#10B981",
        "blue": "#2563EB",
        "yellow": "#F59E0B",
        "red": "#EF4444",
        "dark_red": "#991B1B",
        "default": "#CBD5E1",
    }.get(color, "#CBD5E1")
    title = f"#{rank} · {asset.get('ticker')}" if rank else str(asset.get("ticker") or "-")
    st.markdown(
        f"""
        <div style="background:rgba(255,255,255,.94);border:1px solid {border};border-radius:24px;padding:18px 20px;
                    box-shadow:0 16px 36px rgba(15,23,42,.08);min-height:190px;margin-bottom:12px;">
            <div style="font-size:1.15rem;font-weight:950;color:#0F172A;">{title}</div>
            <div style="color:#64748B;font-size:.88rem;height:38px;overflow:hidden;">{asset.get('name') or '-'}</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0;">
                <span style="padding:5px 10px;border-radius:999px;background:#EFF6FF;color:#1D4ED8;font-weight:900;font-size:.78rem;">{asset.get('asset_class') or '-'}</span>
                <span style="padding:5px 10px;border-radius:999px;background:#F8FAFC;color:#475569;font-weight:900;font-size:.78rem;">{status}</span>
                <span style="padding:5px 10px;border-radius:999px;background:#ECFDF5;color:#047857;font-weight:900;font-size:.78rem;">{tag}</span>
            </div>
            <div style="font-size:2.2rem;font-weight:980;color:{border};line-height:1;">{score:.0f}<span style="font-size:1rem;color:#64748B;">/100</span></div>
            <div style="font-size:.86rem;color:#475569;margin-top:10px;line-height:1.55;">
                Registros: <b>{int(asset.get('price_records') or 0)}</b><br>
                Histórico: {asset.get('first_price_date') or '-'} → {asset.get('last_price_date') or '-'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with dbcompat.connect(ROOT_DIR) as conn:
    conn.row_factory = dbcompat.Row
    ensure_asset_quality_columns(conn)
    if not table_exists(conn, "asset_catalog") or safe_count(conn, "asset_catalog") == 0:
        st.info("asset_catalog ainda está vazio. Importe o Excel seed com: python scripts/import_asset_catalog_from_excel.py --file data/imports/b3.xlsx")
        st.stop()

    summary = get_catalog_summary(conn)
    rel = summary["by_reliability"]
    rec = summary["by_recommendation"]
    classes = summary["by_class"]

    status = summary.get("by_status", {})
    sources = summary.get("by_source", {})
    fonte_mais_usada = max(sources.items(), key=lambda x: x[1])[0] if sources else "-"

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1: render_metric_card("Total", summary["total"], color="blue")
    with c2: render_metric_card("Recomendados", rec.get("recommended", 0), color="green")
    with c3: render_metric_card("Excelentes", rel.get("excellent", 0), color="green")
    with c4: render_metric_card("Bons", rel.get("good", 0), color="blue")
    with c5: render_metric_card("Usáveis", rel.get("usable", 0), color="yellow")
    with c6: render_metric_card("Weak/Stale", rel.get("weak_data", 0) + status.get("stale", 0), color="red")
    with c7: render_metric_card("Inválidos/Pend.", rel.get("invalid", 0) + rel.get("unknown", 0) + status.get("pending_validation", 0), color="dark_red")

    s1, s2, s3, s4, s5, s6 = st.columns(6)
    with s1: render_metric_card("Validados recentes", status.get("active", 0) + status.get("weak_data", 0), color="green")
    with s2: render_metric_card("Pulados por cache", "via script", color="blue")
    with s3: render_metric_card("Stale", status.get("stale", 0), color="yellow")
    with s4: render_metric_card("Weak data", status.get("weak_data", 0) + rel.get("weak_data", 0), color="yellow")
    with s5: render_metric_card("Fonte mais usada", fonte_mais_usada, color="purple")
    with s6: render_metric_card("Última validação", summary.get("last_validation") or "-", color="blue")

    render_section_header("Distribuição por classe", "Visão rápida do universo disponível para análise.")
    cols = st.columns(6)
    for idx, cls in enumerate(["equity", "fii", "etf", "bdr", "crypto", "index"]):
        with cols[idx]:
            render_metric_card(cls.upper(), classes.get(cls, 0), color="purple" if cls in {"etf", "bdr"} else "blue")

    render_section_header("Ativos sugeridos para análise", "Esses ativos possuem maior qualidade de dados e são mais adequados para backtests.")
    top_assets = get_recommended_assets(conn, limit=6)
    if top_assets:
        cards = st.columns(3)
        for idx, asset in enumerate(top_assets):
            with cards[idx % 3]:
                _asset_card(asset, idx + 1)
    else:
        st.warning("Nenhum ativo recomendado ainda. Rode: python scripts/update_asset_quality_scores.py --limit=500")

    render_section_header("Top 5 por categoria")
    for cls in [c for c in ["equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity"] if classes.get(c, 0)]:
        st.markdown(f"### {cls.upper()}")
        top = get_top_assets(conn, asset_class=cls, limit=5)
        cols = st.columns(min(len(top), 5) or 1)
        for idx, asset in enumerate(top):
            with cols[idx % len(cols)]:
                _asset_card(asset, idx + 1)

    render_section_header("Explorar catálogo")
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1.4, .8])
    classes_list = [r[0] for r in conn.execute("SELECT DISTINCT asset_class FROM asset_catalog ORDER BY asset_class").fetchall() if r[0]]
    rel_list = [r[0] for r in conn.execute("SELECT DISTINCT reliability_status FROM asset_catalog ORDER BY reliability_status").fetchall() if r[0]]
    source_list = [r[0] for r in conn.execute("SELECT DISTINCT COALESCE(last_source_used, preferred_source) FROM asset_catalog WHERE COALESCE(last_source_used, preferred_source) IS NOT NULL ORDER BY 1").fetchall() if r[0]]
    status_list = [r[0] for r in conn.execute("SELECT DISTINCT api_status FROM asset_catalog ORDER BY api_status").fetchall() if r[0]]
    asset_class = f1.selectbox("Classe", ["all"] + classes_list)
    reliability = f2.selectbox("Confiabilidade", ["all"] + rel_list)
    source_filter = f3.selectbox("Fonte", ["all"] + source_list)
    search = f4.text_input("Buscar ticker/nome")
    limit = f5.slider("Limite", 20, 2000, 300)
    status_filter = st.selectbox("Status API", ["all"] + status_list, horizontal=True if hasattr(st, "selectbox") else False) if False else "all"

    sql = """
        SELECT ticker, yahoo_symbol, name, asset_class, market, currency, source, api_status,
               preferred_source, last_source_used, source_priority,
               data_quality_score, validation_score, reliability_status, recommendation_tag,
               price_records, history_days, first_price_date, last_price_date, updated_quality_at, last_validated_at, notes
          FROM asset_catalog
         WHERE 1=1
    """
    params = []
    if asset_class != "all":
        sql += " AND asset_class=?"; params.append(asset_class)
    if reliability != "all":
        sql += " AND reliability_status=?"; params.append(reliability)
    if source_filter != "all":
        sql += " AND COALESCE(last_source_used, preferred_source)=?"; params.append(source_filter)
    status_quick = st.radio("Filtro rápido", ["Todos", "Stale", "Weak data", "Sem fonte"], horizontal=True)
    if status_quick == "Stale":
        sql += " AND api_status='stale'"
    elif status_quick == "Weak data":
        sql += " AND (api_status='weak_data' OR reliability_status='weak_data')"
    elif status_quick == "Sem fonte":
        sql += " AND COALESCE(last_source_used, preferred_source, '')=''"
    if search:
        sql += " AND (ticker LIKE ? OR name LIKE ? OR yahoo_symbol LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    df = pd.read_sql_query(sql + " ORDER BY data_quality_score DESC, validation_score DESC, price_records DESC LIMIT ?", conn, params=params + [limit])

    avoid = get_assets_to_avoid(conn, limit=10)
    with st.expander("Ativos a evitar / revisar"):
        st.dataframe(pd.DataFrame(avoid), use_container_width=True, hide_index=True)

    with st.expander("Ver catálogo completo"):
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("Atualize qualidade com: python scripts/update_asset_quality_scores.py --limit=500")

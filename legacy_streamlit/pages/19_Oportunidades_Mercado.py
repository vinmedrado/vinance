from __future__ import annotations
import pandas as pd
import streamlit as st
from services.auth_middleware import check_auth
from services.final_ranking_service import get_ranked_assets_by_market
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout

st.set_page_config(page_title="FinanceOS · Oportunidades", layout="wide")
inject_global_css(); user=check_auth(); tenant_id=user.get('tenant_id')
render_hero("Oportunidades de mercado", "Ranking traduzido para score, risco, confiança e motivo da oportunidade.", eyebrow="Investimentos", status="ML, backtests e ranking ficam nos bastidores")
market_options={"Ações":"equity","FIIs":"fii","ETFs":"etf","BDRs":"bdr","Cripto":"crypto"}
selected=st.selectbox("Mercado", list(market_options.keys()))
show=st.toggle("Modo auditoria: mostrar ativos incompletos", value=False)
try:
    ranked=get_ranked_assets_by_market(market_options[selected], limit=100, tenant_id=tenant_id, include_ineligible=show)
except Exception as exc:
    ranked=[]; st.info("Ainda não foi possível carregar o ranking real. O modo Admin pode sincronizar dados, ML e backtests.")
if not ranked:
    render_empty_state("Sem oportunidades calculadas", "Alimente catálogo, histórico, ML e backtests no modo Admin. Para o cliente final, esta tela fica limpa e sem erro técnico.", "Abrir Orquestrador", "legacy_streamlit/pages/13_Orquestrador_Geral.py")
    st.stop()
leader=ranked[0]
render_section_header(f"Melhor oportunidade em {selected}")
c1,c2,c3,c4=st.columns(4)
with c1: render_metric_card("Ativo", leader.get('ticker','-'), color="green")
with c2: render_metric_card("Score", f"{leader.get('score_final',0):.0f}/100", color="green")
with c3: render_metric_card("Confiança", f"{leader.get('confidence',0):.2f}", color="blue")
with c4: render_metric_card("Risco", leader.get('risk_label','Controlado'), color="yellow")
render_callout("Motivo", leader.get('explanation') or "Combinação de qualidade de dados, sinais quantitativos e histórico.", "info")
df=pd.DataFrame(ranked).head(10)
cols=[c for c in ['ticker','score_final','classification','confidence','risk_score','data_completeness_score','eligible'] if c in df.columns]
st.dataframe(df[cols], use_container_width=True, hide_index=True)
st.caption("Não é recomendação financeira. Use como apoio educacional e analítico.")

import pandas as pd
import streamlit as st

from services.ui_helpers import format_money, format_number, format_percent, get_connection, parse_json, safe_query
from services.strategy_interpreter import (
    calculate_strategy_score,
    classify_strategy,
    generate_recommendations,
    summarize_strategy,
)
from services.strategy_comparator import (
    compare_to_average,
    compare_to_best,
    compare_to_benchmarks,
    get_top_strategies,
    load_backtest_metrics,
    rank_backtests,
    summarize_comparison,
)
from services.benchmark_service import calculate_alpha, get_benchmark_data
from services.strategy_storytelling import generate_story
from services.ui_components import (
    inject_global_css,
    render_badge,
    render_hero,
    render_metric_card,
    render_metric_row,
    render_section_header,
    render_strategy_card,
    render_top5_cards,
)

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
st.set_page_config(page_title="FinanceOS · Backtests", layout="wide")
inject_global_css()
render_section_header(
    "Backtests",
    "Compare estratégias, acompanhe ranking visual, veja métricas e entenda quais configurações parecem mais robustas.",
)

base = safe_query("""
SELECT
    br.id,
    br.strategy_name AS strategy,
    br.asset_class,
    br.start_date,
    br.end_date,
    br.top_n,
    br.rebalance_frequency,
    br.status,
    br.created_at,
    br.finished_at,
    br.initial_capital,
    br.params_json,
    bm.total_return,
    bm.annual_return,
    bm.max_drawdown,
    bm.sharpe_ratio,
    bm.win_rate,
    bm.total_trades,
    bm.turnover,
    bm.metrics_json
FROM backtest_runs br
LEFT JOIN backtest_metrics bm ON bm.backtest_id = br.id
ORDER BY br.id DESC
""")

if base.empty:
    st.info("Nenhum backtest salvo ainda. Rode uma estratégia na página 'Criar Estratégia' ou 'Executar Backtest'.")
    st.stop()


def _final_value(row):
    data = parse_json(row.get("metrics_json"))
    for key in ["final_value", "final_equity", "equity_final"]:
        if key in data:
            return data[key]
    try:
        return float(row.get("initial_capital") or 0) * (1 + float(row.get("total_return") or 0))
    except Exception:
        return None


base["final_value"] = base.apply(_final_value, axis=1)
base["strategy_ui_score"] = base.apply(lambda r: calculate_strategy_score(r.to_dict()), axis=1)

with get_connection() as conn:
    all_backtests = load_backtest_metrics(conn)
ranked_backtests = rank_backtests(all_backtests)

if ranked_backtests:
    best_preview = ranked_backtests[0]
    render_hero(
        "Melhor estratégia atual",
        f"{best_preview.get('strategy') or best_preview.get('strategy_name') or 'Estratégia'} · Top N {best_preview.get('top_n', '-')}",
        eyebrow="Backtests · Ranking Premium",
        status=f"Retorno {format_percent(best_preview.get('total_return'))} | Sharpe {float(best_preview.get('sharpe_ratio') or 0):.2f} | DD {format_percent(best_preview.get('max_drawdown'))}",
        metrics={
            "Score": f"{int(best_preview.get('comparison_score') or calculate_strategy_score(best_preview))}/100",
            "Turnover": f"{float(best_preview.get('turnover') or 0):.2f}",
            "Trades": format_number(best_preview.get('total_trades'), 0) if 'format_number' in globals() else str(best_preview.get('total_trades', '-')),
        },
    )

st.markdown("### Ranking de Estratégias")
if ranked_backtests:
    best_overall = ranked_backtests[0]
    best_return = max(ranked_backtests, key=lambda x: float(x.get("total_return") or 0))
    best_sharpe = max(ranked_backtests, key=lambda x: float(x.get("sharpe_ratio") or 0))
    best_dd = max(ranked_backtests, key=lambda x: float(x.get("max_drawdown") or -999))
    best_turnover = min(ranked_backtests, key=lambda x: float(x.get("turnover") or 999999))

    st.markdown("#### Melhor estratégia geral")
    render_strategy_card(best_overall, rank=1, highlight=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Retorno médio", format_percent(base["total_return"].mean()), "Média dos backtests", "blue")
    with c2:
        render_metric_card("Melhor retorno", format_percent(best_return.get("total_return")), f"#{best_return.get('id')}", "green")
    with c3:
        render_metric_card("Melhor Sharpe", f"{float(best_sharpe.get('sharpe_ratio') or 0):.2f}", f"#{best_sharpe.get('id')}", "blue")
    with c4:
        render_metric_card("Menor drawdown", format_percent(best_dd.get("max_drawdown")), f"#{best_dd.get('id')}", "yellow")
    with c5:
        render_metric_card("Menor turnover", f"{float(best_turnover.get('turnover') or 0):.2f}", f"#{best_turnover.get('id')}", "default")

    st.markdown("---")
    st.markdown("### Top 5 visual")
    render_top5_cards(get_top_strategies(ranked_backtests, limit=5))
else:
    st.info("Ainda não há métricas suficientes para ranking.")

st.markdown("---")
st.markdown("### Consulta detalhada")
f1, f2, f3, f4 = st.columns(4)
strategy = f1.selectbox("Strategy", ["Todos"] + sorted(base["strategy"].dropna().unique().tolist()))
asset_class = f2.selectbox("Asset class", ["Todos"] + sorted(base["asset_class"].dropna().unique().tolist()))
status = f3.selectbox("Status", ["Todos"] + sorted(base["status"].dropna().unique().tolist()))
top_n_values = ["Todos"] + sorted([int(x) for x in base["top_n"].dropna().unique().tolist()])
top_n = f4.selectbox("Top N", top_n_values)

sort_option = st.selectbox("Ordenar por", ["Mais recente", "Retorno", "Sharpe", "Drawdown", "Turnover", "Score visual"])
filtered = base.copy()
if strategy != "Todos":
    filtered = filtered[filtered["strategy"] == strategy]
if asset_class != "Todos":
    filtered = filtered[filtered["asset_class"] == asset_class]
if status != "Todos":
    filtered = filtered[filtered["status"] == status]
if top_n != "Todos":
    filtered = filtered[filtered["top_n"] == top_n]

sort_map = {
    "Mais recente": ("id", False),
    "Retorno": ("total_return", False),
    "Sharpe": ("sharpe_ratio", False),
    "Drawdown": ("max_drawdown", False),
    "Turnover": ("turnover", True),
    "Score visual": ("strategy_ui_score", False),
}
col, asc = sort_map[sort_option]
filtered = filtered.sort_values(col, ascending=asc)

cols = ["id", "strategy", "asset_class", "start_date", "end_date", "top_n", "rebalance_frequency", "status", "total_return", "annual_return", "max_drawdown", "sharpe_ratio", "win_rate", "total_trades", "turnover", "strategy_ui_score", "final_value"]
with st.expander("Ver dados detalhados dos backtests", expanded=False):
    st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### Detalhe do backtest")
ids = filtered["id"].astype(int).tolist()
if not ids:
    st.info("Nenhum backtest para os filtros atuais.")
    st.stop()
selected_id = st.selectbox("Selecionar backtest", ids, index=0)
row = base[base["id"] == selected_id].iloc[0]

selected_metrics = {
    "id": int(row.get("id")),
    "strategy": row.get("strategy"),
    "asset_class": row.get("asset_class"),
    "top_n": row.get("top_n"),
    "total_return": row.get("total_return"),
    "annual_return": row.get("annual_return"),
    "max_drawdown": row.get("max_drawdown"),
    "sharpe_ratio": row.get("sharpe_ratio"),
    "win_rate": row.get("win_rate"),
    "total_trades": row.get("total_trades"),
    "turnover": row.get("turnover"),
    "final_value": row.get("final_value"),
}
benchmark = get_benchmark_data(row.get("start_date"), row.get("end_date"))
alpha_ibov = calculate_alpha(selected_metrics.get("total_return"), benchmark.get("ibov_return"))
alpha_cdi = calculate_alpha(selected_metrics.get("total_return"), benchmark.get("cdi_return"))
benchmark_compare = compare_to_benchmarks(selected_metrics, benchmark)
story_text = generate_story(selected_metrics, benchmark)

classification = classify_strategy(selected_metrics)
score_ui = calculate_strategy_score(selected_metrics)
summary_text = summarize_strategy(selected_metrics)
recommendations = generate_recommendations(selected_metrics)
comparison_best = compare_to_best(selected_metrics, ranked_backtests)
comparison_avg = compare_to_average(selected_metrics, ranked_backtests)
comparison_summary = summarize_comparison(selected_metrics, ranked_backtests)

h1, h2, h3 = st.columns([1.3, 1, 1])
with h1:
    render_strategy_card({**selected_metrics, "comparison_score": score_ui}, highlight=True)
with h2:
    render_metric_card("Score UI", f"{score_ui}/100", "Avaliação visual", "green" if score_ui >= 70 else "yellow" if score_ui >= 45 else "red")
with h3:
    render_metric_card("Valor final", format_money(row["final_value"]), "Capital após backtest", "blue")

st.markdown("#### Métricas principais")
render_metric_row(selected_metrics)

st.markdown("#### Benchmark de mercado")
bm1, bm2, bm3, bm4 = st.columns(4)
with bm1:
    render_metric_card("Retorno Estratégia", format_percent(selected_metrics.get("total_return")), "Resultado do backtest", "green" if float(selected_metrics.get("total_return") or 0) >= 0 else "red")
with bm2:
    render_metric_card("IBOV", format_percent(benchmark.get("ibov_return")), "Benchmark mercado", "blue")
with bm3:
    render_metric_card("CDI", format_percent(benchmark.get("cdi_return")), "CDI estimado", "light_blue")
with bm4:
    render_metric_card("Alpha vs IBOV", format_percent(alpha_ibov), f"vs CDI: {format_percent(alpha_cdi)}", "green" if alpha_ibov >= 0 else "red")

st.markdown("#### Interpretação do Resultado")
st.info(story_text)

st.markdown("#### Interpretação automática")
render_badge(classification.get("label", "-"))
message = f"**{classification.get('label', '-')}** — {summary_text}"
level = classification.get("level")
if level == "success":
    st.success(message)
elif level == "warning":
    st.warning(message)
elif level == "error":
    st.error(message)
else:
    st.info(message)

st.markdown("#### Comparação com outras estratégias")
if comparison_best.get("has_comparison"):
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Posição no ranking", f"{comparison_best.get('position')}/{comparison_best.get('total')}")
    b2.metric("Diferença para maior retorno", format_percent(comparison_best.get("diff_to_best_return")))
    b3.metric("Diferença para melhor Sharpe", f"{float(comparison_best.get('diff_to_best_sharpe') or 0):.2f}")
    b4.metric("Diferença para melhor score", f"{float(comparison_best.get('diff_to_best_score') or 0):.0f} pts")
    c1, c2 = st.columns(2)
    c1.metric("Diferença para IBOV", format_percent(benchmark_compare.get("diff_to_ibov")))
    c2.metric("Diferença para CDI", format_percent(benchmark_compare.get("diff_to_cdi")))

    if comparison_avg.get("has_comparison"):
        if comparison_avg.get("score_above_avg") and not comparison_avg.get("drawdown_worse_avg"):
            st.success(comparison_summary)
        elif comparison_avg.get("score_above_avg"):
            st.warning(comparison_summary)
        else:
            st.info(comparison_summary)
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Retorno vs média", format_percent(comparison_avg.get("diff_return_avg")))
        a2.metric("Sharpe vs média", f"{float(comparison_avg.get('diff_sharpe_avg') or 0):.2f}")
        a3.metric("Turnover vs média", f"{float(comparison_avg.get('diff_turnover_avg') or 0):.2f}")
        a4.metric("Drawdown vs média", format_percent(comparison_avg.get("diff_drawdown_avg")))
else:
    st.info("Ainda não há outros backtests suficientes para comparar.")

st.markdown("#### Recomendações")
for rec in recommendations:
    st.write(f"- {rec}")

st.markdown("---")
equity = safe_query("SELECT date, equity_value, cash, positions_value FROM backtest_equity_curve WHERE backtest_id = ? ORDER BY date", (int(selected_id),))
if not equity.empty:
    st.subheader("Curva de equity")
    st.line_chart(equity.set_index("date")[["equity_value"]])
else:
    st.info("Equity curve não encontrada para este backtest.")

trades = safe_query("SELECT ticker, action, date, price, quantity, gross_value, transaction_cost, net_value FROM backtest_trades WHERE backtest_id = ? ORDER BY date, id", (int(selected_id),))
if not trades.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Trades")
        st.dataframe(trades, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Ativos mais negociados")
        traded = trades.groupby("ticker").size().reset_index(name="trades").sort_values("trades", ascending=False)
        st.bar_chart(traded.set_index("ticker"))
        st.dataframe(traded, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum trade encontrado para este backtest.")

with st.expander("Parâmetros salvos"):
    st.json(parse_json(row.get("params_json")))

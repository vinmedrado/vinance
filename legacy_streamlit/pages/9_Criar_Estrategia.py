from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Any, Dict

import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.strategies.strategy_runner import StrategyBacktestRunner
from services.ui_helpers import format_money, format_percent, get_connection
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
)

st.set_page_config(page_title="FinanceOS · Criar Estratégia", layout="wide")
inject_global_css()

PRESETS: Dict[str, Dict[str, Any]] = {
    "Conservador": {
        "top_n": 5,
        "weight_return": 0.35,
        "weight_trend": 0.25,
        "weight_risk": 0.40,
        "weight_liquidity": 0.00,
        "weight_dividend": 0.00,
        "max_position_pct": 0.12,
        "cash_buffer_pct": 0.15,
        "selection_penalty_factor": 4.0,
        "min_holding_period_rebalances": 3,
        "rebalance_threshold_pct": 0.30,
        "rebalance_skip_enabled": True,
        "rebalance_skip_max_changes": 0,
        "descricao": "Prioriza controle de risco, caixa maior e menor rotação.",
    },
    "Balanceado": {
        "top_n": 5,
        "weight_return": 0.50,
        "weight_trend": 0.30,
        "weight_risk": 0.20,
        "weight_liquidity": 0.00,
        "weight_dividend": 0.00,
        "max_position_pct": 0.15,
        "cash_buffer_pct": 0.10,
        "selection_penalty_factor": 4.0,
        "min_holding_period_rebalances": 2,
        "rebalance_threshold_pct": 0.20,
        "rebalance_skip_enabled": True,
        "rebalance_skip_max_changes": 1,
        "descricao": "Busca equilíbrio entre retorno, tendência e estabilidade.",
    },
    "Agressivo": {
        "top_n": 6,
        "weight_return": 0.60,
        "weight_trend": 0.25,
        "weight_risk": 0.15,
        "weight_liquidity": 0.00,
        "weight_dividend": 0.00,
        "max_position_pct": 0.20,
        "cash_buffer_pct": 0.05,
        "selection_penalty_factor": 4.0,
        "min_holding_period_rebalances": 1,
        "rebalance_threshold_pct": 0.15,
        "rebalance_skip_enabled": True,
        "rebalance_skip_max_changes": 1,
        "descricao": "Prioriza retorno e aceita mais oscilação.",
    },
}

OBJECTIVE_HINTS = {
    "Reduzir risco": "Use perfil Conservador ou aumente peso de risco, caixa e min hold.",
    "Equilibrar risco e retorno": "Use perfil Balanceado como ponto de partida.",
    "Maximizar retorno": "Use perfil Agressivo, mas acompanhe drawdown e turnover.",
}


def run_backtest(params: Dict[str, Any]) -> Dict[str, Any]:
    runner = StrategyBacktestRunner()
    return runner.run(**params)


render_hero(
    "Criar Estratégia",
    "Monte, simule e interprete uma estratégia quantitativa com experiência guiada.",
    eyebrow="Strategy Builder",
    status="Perfil · Universo · Risco · Simulação",
)

st.markdown("### 1. Perfil")
profile = st.radio("Escolha o perfil da estratégia", list(PRESETS.keys()), horizontal=True, index=1)
preset = PRESETS[profile]
st.info(preset["descricao"])

st.markdown("### 2. Objetivo")
objective = st.selectbox("Qual objetivo principal?", ["Reduzir risco", "Equilibrar risco e retorno", "Maximizar retorno"], index=1)
st.caption(OBJECTIVE_HINTS.get(objective, ""))

st.markdown("### 3. Universo e período")
col1, col2, col3 = st.columns(3)
asset_class = col1.selectbox("Classe de ativo", ["equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity", "all"], index=0)
top_n = int(col2.number_input("Quantidade de ativos (top_n)", min_value=1, max_value=50, value=int(preset["top_n"]), step=1))
initial_capital = float(col3.number_input("Capital inicial", min_value=100.0, value=10000.0, step=1000.0))

col4, col5, col6 = st.columns(3)
start_date = col4.date_input("Data inicial", value=date(2020, 1, 1))
end_date = col5.date_input("Data final", value=date(2024, 1, 1))
mode = col6.selectbox("Modo", ["research", "no_lookahead"], index=0)

st.markdown("### 4. Parâmetros avançados")
with st.expander("Editar parâmetros avançados", expanded=False):
    st.markdown("#### Pesos da estratégia")
    w1, w2, w3, w4, w5 = st.columns(5)
    weight_return = float(w1.number_input("weight_return", min_value=0.0, max_value=1.0, value=float(preset["weight_return"]), step=0.05))
    weight_trend = float(w2.number_input("weight_trend", min_value=0.0, max_value=1.0, value=float(preset["weight_trend"]), step=0.05))
    weight_risk = float(w3.number_input("weight_risk", min_value=0.0, max_value=1.0, value=float(preset["weight_risk"]), step=0.05))
    weight_liquidity = float(w4.number_input("weight_liquidity", min_value=0.0, max_value=1.0, value=float(preset["weight_liquidity"]), step=0.05))
    weight_dividend = float(w5.number_input("weight_dividend", min_value=0.0, max_value=1.0, value=float(preset["weight_dividend"]), step=0.05))

    st.markdown("#### Risco e rotação")
    p1, p2, p3, p4 = st.columns(4)
    max_position_pct = float(p1.number_input("max_position_pct", min_value=0.01, max_value=1.0, value=float(preset["max_position_pct"]), step=0.01))
    cash_buffer_pct = float(p2.number_input("cash_buffer_pct", min_value=0.0, max_value=0.9, value=float(preset["cash_buffer_pct"]), step=0.01))
    selection_penalty_factor = float(p3.number_input("selection_penalty_factor", min_value=0.0, max_value=20.0, value=float(preset["selection_penalty_factor"]), step=0.5))
    min_holding_period_rebalances = int(p4.number_input("min_holding_period_rebalances", min_value=0, max_value=24, value=int(preset["min_holding_period_rebalances"]), step=1))

    p5, p6, p7 = st.columns(3)
    rebalance_threshold_pct = float(p5.number_input("rebalance_threshold_pct", min_value=0.0, max_value=1.0, value=float(preset["rebalance_threshold_pct"]), step=0.01))
    rebalance_skip_enabled = bool(p6.checkbox("rebalance_skip_enabled", value=bool(preset["rebalance_skip_enabled"])))
    rebalance_skip_max_changes = int(p7.number_input("rebalance_skip_max_changes", min_value=0, max_value=20, value=int(preset["rebalance_skip_max_changes"]), step=1))

    st.markdown("#### Execução")
    e1, e2 = st.columns(2)
    rebalance_frequency = e1.selectbox("Rebalanceamento", ["monthly", "weekly", "daily"], index=0)
    transaction_cost = float(e2.number_input("transaction_cost", min_value=0.0, max_value=0.05, value=0.001, step=0.001, format="%.4f"))

st.markdown("### 5. Simulação")
summary_cols = st.columns(4)
summary_cols[0].metric("Perfil", profile)
summary_cols[1].metric("Objetivo", objective)
summary_cols[2].metric("Classe", asset_class)
summary_cols[3].metric("Top N", top_n)

params = {
    "strategy": "multi_factor",
    "asset_class": asset_class,
    "start_date": str(start_date),
    "end_date": str(end_date),
    "initial_capital": initial_capital,
    "top_n": top_n,
    "rebalance_frequency": locals().get("rebalance_frequency", "monthly"),
    "transaction_cost": locals().get("transaction_cost", 0.001),
    "mode": mode,
    "dry_run": False,
    "weight_return": weight_return,
    "weight_trend": weight_trend,
    "weight_risk": weight_risk,
    "weight_liquidity": weight_liquidity,
    "weight_dividend": weight_dividend,
    "max_position_pct": max_position_pct,
    "cash_buffer_pct": cash_buffer_pct,
    "selection_penalty_factor": selection_penalty_factor,
    "min_holding_period_rebalances": min_holding_period_rebalances,
    "rebalance_threshold_pct": rebalance_threshold_pct,
    "rebalance_skip_enabled": rebalance_skip_enabled,
    "rebalance_skip_max_changes": rebalance_skip_max_changes,
}

with st.expander("Parâmetros que serão enviados ao runner"):
    st.json(params)

if st.button("Simular Estratégia", type="primary", use_container_width=True):
    try:
        if start_date >= end_date:
            st.error("A data inicial precisa ser menor que a data final.")
        else:
            with st.spinner("Rodando simulação com a engine existente..."):
                result = run_backtest(params)
            metrics = result.get("metrics", {}) or {}
            score_ui = calculate_strategy_score(metrics)
            classification = classify_strategy(metrics)
            recommendations = generate_recommendations(metrics)
            summary_text = summarize_strategy(metrics)
            benchmark = get_benchmark_data(params.get("start_date"), params.get("end_date"))
            alpha_ibov = calculate_alpha(metrics.get("total_return"), benchmark.get("ibov_return"))
            alpha_cdi = calculate_alpha(metrics.get("total_return"), benchmark.get("cdi_return"))
            benchmark_compare = compare_to_benchmarks(metrics, benchmark)
            story_text = generate_story(metrics, benchmark)
            st.success("Simulação finalizada e salva no banco.")

            render_hero(
                "Resultado da Estratégia",
                f"{classification.get('label', '-')} · Backtest #{result.get('backtest_id', '-')}",
                eyebrow="Simulação concluída",
                status=f"Retorno {format_percent(metrics.get('total_return'))} | Sharpe {float(metrics.get('sharpe_ratio') or 0):.2f} | DD {format_percent(metrics.get('max_drawdown'))}",
                metrics={
                    "Score": f"{score_ui}/100",
                    "IBOV": format_percent(benchmark.get("ibov_return")),
                    "CDI": format_percent(benchmark.get("cdi_return")),
                    "Alpha": format_percent(alpha_ibov),
                    "Valor final": format_money(metrics.get('final_value') or metrics.get('final_equity')),
                },
            )

            st.markdown("---")
            st.markdown("## Resultado da Estratégia")
            top_a, top_b, top_c = st.columns([1.1, 1, 1])
            with top_a:
                render_metric_card("Score da Estratégia", f"{score_ui}/100", "Score visual da UI", "green" if score_ui >= 70 else "yellow" if score_ui >= 45 else "red")
            with top_b:
                render_metric_card("Retorno total", format_percent(metrics.get("total_return")), "Resultado acumulado", "green" if float(metrics.get("total_return") or 0) > 0 else "red")
            with top_c:
                render_metric_card("Valor final", format_money(metrics.get("final_value") or metrics.get("final_equity")), f"Backtest #{result.get('backtest_id', '-')}", "blue")

            render_badge(classification.get("label", "-"))
            st.markdown("### Métricas principais")
            render_metric_row(metrics)

            st.markdown("### Benchmark de mercado")
            bm1, bm2, bm3, bm4 = st.columns(4)
            with bm1:
                render_metric_card("Retorno Estratégia", format_percent(metrics.get("total_return")), "Resultado do backtest", "green" if float(metrics.get("total_return") or 0) >= 0 else "red")
            with bm2:
                render_metric_card("IBOV", format_percent(benchmark.get("ibov_return")), "Benchmark mercado", "blue")
            with bm3:
                render_metric_card("CDI", format_percent(benchmark.get("cdi_return")), "CDI estimado", "light_blue")
            with bm4:
                render_metric_card("Alpha vs IBOV", format_percent(alpha_ibov), f"vs CDI: {format_percent(alpha_cdi)}", "green" if alpha_ibov >= 0 else "red")

            st.markdown("---")
            st.markdown("### Interpretação do Resultado")
            st.info(story_text)

            st.markdown("### Leitura automática")
            level = classification.get("level")
            if level == "success":
                st.success(summary_text)
            elif level == "warning":
                st.warning(summary_text)
            elif level == "error":
                st.error(summary_text)
            else:
                st.info(summary_text)

            st.markdown("#### Recomendações")
            for rec in recommendations:
                st.write(f"- {rec}")

            st.markdown("---")
            st.markdown("### Comparação com histórico")
            current_metrics = dict(metrics)
            current_metrics["id"] = result.get("backtest_id")
            current_metrics["backtest_id"] = result.get("backtest_id")
            current_metrics["strategy"] = params.get("strategy")
            current_metrics["asset_class"] = params.get("asset_class")
            current_metrics["top_n"] = params.get("top_n")
            with get_connection() as conn:
                all_backtests = load_backtest_metrics(conn)
            ranked = rank_backtests(all_backtests)
            comparison_best = compare_to_best(current_metrics, ranked)
            comparison_avg = compare_to_average(current_metrics, ranked)
            comparison_summary = summarize_comparison(current_metrics, ranked)

            if comparison_best.get("has_comparison"):
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Posição estimada", f"{comparison_best.get('position')}/{comparison_best.get('total')}")
                p2.metric("Retorno vs melhor", format_percent(comparison_best.get("diff_to_best_return")))
                p3.metric("Sharpe vs melhor", f"{float(comparison_best.get('diff_to_best_sharpe') or 0):.2f}")
                p4.metric("Score vs melhor", f"{float(comparison_best.get('diff_to_best_score') or 0):.0f} pts")
                b1, b2 = st.columns(2)
                b1.metric("Diferença para IBOV", format_percent(benchmark_compare.get("diff_to_ibov")))
                b2.metric("Diferença para CDI", format_percent(benchmark_compare.get("diff_to_cdi")))

                if comparison_avg.get("score_above_avg") and not comparison_avg.get("drawdown_worse_avg"):
                    st.success("Melhor que a média — " + comparison_summary)
                elif comparison_avg.get("score_above_avg"):
                    st.warning("Boa, mas arriscada — " + comparison_summary)
                else:
                    st.info("Abaixo da média ou precisa de mais validação — " + comparison_summary)

                a1, a2, a3, a4 = st.columns(4)
                a1.metric("Retorno vs média", format_percent(comparison_avg.get("diff_return_avg")))
                a2.metric("Sharpe vs média", f"{float(comparison_avg.get('diff_sharpe_avg') or 0):.2f}")
                a3.metric("Turnover vs média", f"{float(comparison_avg.get('diff_turnover_avg') or 0):.2f}")
                a4.metric("Drawdown vs média", format_percent(comparison_avg.get("diff_drawdown_avg")))
            else:
                st.info("Ainda não há histórico suficiente para comparar. Rode mais backtests para criar ranking.")

            with st.expander("Ver detalhes técnicos"):
                st.json(result)
    except Exception as exc:
        st.error("Erro ao simular estratégia. Verifique se há dados, métricas e scores suficientes no banco.")
        st.exception(exc)

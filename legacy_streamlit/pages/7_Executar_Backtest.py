from datetime import date
from pathlib import Path
import sys

import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.strategies.strategy_runner import StrategyBacktestRunner
from services.ui_helpers import format_money, format_percent

st.set_page_config(page_title="FinanceOS · Executar Backtest", layout="wide")
st.title("Executar Backtest")
st.caption("Executa a mesma lógica do script `scripts/run_strategy_backtest.py`, sem duplicar regra de negócio.")

with st.form("backtest_form"):
    c1, c2, c3, c4 = st.columns(4)
    strategy = c1.selectbox("strategy", ["multi_factor", "score_top_n", "momentum", "dividend_yield", "low_volatility"])
    asset_class = c2.selectbox("asset_class", ["equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity", "all"])
    top_n = c3.number_input("top_n", min_value=1, max_value=50, value=5, step=1)
    mode = c4.selectbox("mode", ["research", "no_lookahead"])

    c5, c6, c7, c8 = st.columns(4)
    start_date = c5.date_input("start_date", value=date(2020, 1, 1))
    end_date = c6.date_input("end_date", value=date(2024, 1, 1))
    initial_capital = c7.number_input("initial_capital", min_value=100.0, value=10000.0, step=1000.0)
    rebalance = c8.selectbox("rebalance", ["monthly", "weekly", "daily"])

    st.markdown("#### Pesos")
    w1, w2, w3, w4, w5 = st.columns(5)
    weight_return = w1.number_input("weight_return", value=0.5, step=0.05)
    weight_trend = w2.number_input("weight_trend", value=0.3, step=0.05)
    weight_risk = w3.number_input("weight_risk", value=0.2, step=0.05)
    weight_liquidity = w4.number_input("weight_liquidity", value=0.0, step=0.05)
    weight_dividend = w5.number_input("weight_dividend", value=0.0, step=0.05)

    st.markdown("#### Controles recentes")
    p1, p2, p3, p4 = st.columns(4)
    transaction_cost = p1.number_input("transaction_cost", value=0.001, step=0.001, format="%.4f")
    max_position_pct = p2.number_input("max_position_pct", value=0.15, min_value=0.01, max_value=1.0, step=0.01)
    cash_buffer_pct = p3.number_input("cash_buffer_pct", value=0.10, min_value=0.0, max_value=0.9, step=0.01)
    selection_penalty_factor = p4.number_input("selection_penalty_factor", value=4.0, step=0.5)

    p5, p6, p7, p8 = st.columns(4)
    min_holding_period_rebalances = p5.number_input("min_holding_period_rebalances", value=2, min_value=0, max_value=24, step=1)
    rebalance_threshold_pct = p6.number_input("rebalance_threshold_pct", value=0.20, min_value=0.0, max_value=1.0, step=0.01)
    rebalance_skip_enabled = p7.checkbox("rebalance_skip_enabled", value=True)
    rebalance_skip_max_changes = p8.number_input("rebalance_skip_max_changes", value=1, min_value=0, max_value=20, step=1)

    dry_run = st.checkbox("dry_run", value=False)
    submitted = st.form_submit_button("Rodar Backtest")

if submitted:
    try:
        with st.spinner("Executando backtest..."):
            runner = StrategyBacktestRunner()
            result = runner.run(
                strategy=strategy,
                asset_class=asset_class,
                start_date=str(start_date),
                end_date=str(end_date),
                initial_capital=float(initial_capital),
                top_n=int(top_n),
                rebalance_frequency=rebalance,
                transaction_cost=float(transaction_cost),
                max_position_pct=float(max_position_pct),
                mode=mode,
                dry_run=dry_run,
                weight_return=float(weight_return),
                weight_trend=float(weight_trend),
                weight_risk=float(weight_risk),
                weight_liquidity=float(weight_liquidity),
                weight_dividend=float(weight_dividend),
                cash_buffer_pct=float(cash_buffer_pct),
                selection_penalty_factor=float(selection_penalty_factor),
                min_holding_period_rebalances=int(min_holding_period_rebalances),
                rebalance_threshold_pct=float(rebalance_threshold_pct),
                rebalance_skip_enabled=bool(rebalance_skip_enabled),
                rebalance_skip_max_changes=int(rebalance_skip_max_changes),
            )
        st.success("Backtest finalizado.")
        metrics = result.get("metrics", {})
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("backtest_id", result.get("backtest_id", "-"))
        c2.metric("retorno", format_percent(metrics.get("total_return")))
        c3.metric("drawdown", format_percent(metrics.get("max_drawdown")))
        sharpe_value = metrics.get("sharpe_ratio")
        c4.metric("Sharpe", f"{float(sharpe_value):.2f}" if sharpe_value is not None else "-")
        c5.metric("win rate", format_percent(metrics.get("win_rate")))
        c6.metric("trades", metrics.get("total_trades", result.get("trades", 0)))
        c7, c8 = st.columns(2)
        c7.metric("turnover", f"{metrics.get('turnover', 0):.2f}")
        c8.metric("final_value", format_money(metrics.get("final_value") or metrics.get("final_equity")))
        with st.expander("Resultado bruto"):
            st.json(result)
    except Exception as exc:
        st.error("Erro ao executar backtest. Verifique parâmetros e dados disponíveis.")
        st.exception(exc)

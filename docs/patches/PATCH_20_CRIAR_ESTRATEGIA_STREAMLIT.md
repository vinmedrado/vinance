# PATCH 20 — Criar Estratégia na Interface Streamlit

Implementa `pages/9_Criar_Estrategia.py` como wizard guiado para criação e simulação de estratégia.

- Presets: Conservador, Balanceado e Agressivo
- Objetivos: reduzir risco, equilibrar risco/retorno e maximizar retorno
- Parâmetros avançados em expander
- Execução via `StrategyBacktestRunner`
- Resultado simplificado com retorno, drawdown, Sharpe, win rate, trades, turnover e valor final
- Score visual de UI 0–100 sem persistência no banco

Não altera backtest, banco, scripts, `multi_factor.py` ou `strategy_runner.py`.

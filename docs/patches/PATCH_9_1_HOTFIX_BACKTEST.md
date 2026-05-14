# FinanceOS PATCH 9.1 HOTFIX — Backtest Engine

Correção focada no problema de backtests com `trades = 0`, `total_return = 0` e sem diagnóstico claro.

## O que foi ajustado

- Logs de diagnóstico por rebalanceamento no terminal e em `logs/backtest.log`.
- Estratégia `score_top_n` agora tenta `asset_rankings` e, se não houver ranking válido, cai para `asset_scores`.
- `min_score=None` não filtra indevidamente.
- Novo modo `--mode`:
  - `no_lookahead` mantém a regra segura: usa somente scores/rankings com `calculated_at <= data simulada`.
  - `research` usa scores/rankings atuais sobre o histórico para validar execução, trades, equity curve e métricas.
- Executor instrumentado:
  - target allocation
  - preços D+1
  - ordens geradas
  - ordens executadas
  - motivos de ordens ignoradas

## Comandos principais

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --limit=5 --mode=research
```

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --limit=5 --mode=no_lookahead
```

No modo `research`, o terminal imprime:

> MODO RESEARCH: usa scores atuais sobre histórico. Não é backtest sem viés.

## Arquivos alterados

- `backend/app/backtest/diagnostics.py`
- `backend/app/backtest/backtest_repository.py`
- `backend/app/backtest/backtest_engine.py`
- `backend/app/backtest/strategy_score_top_n.py`
- `backend/app/backtest/strategies/_common.py`
- `backend/app/backtest/strategies/score_top_n.py`
- `backend/app/backtest/strategies/strategy_runner.py`
- `scripts/run_backtest.py`
- `scripts/run_strategy_backtest.py`

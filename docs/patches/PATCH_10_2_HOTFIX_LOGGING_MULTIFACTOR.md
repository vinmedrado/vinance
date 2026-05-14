# PATCH 10.2 — Hotfix logging multi_factor/backtest

Correção cirúrgica do erro:

`TypeError: BacktestDiagnostics.info() got multiple values for keyword argument 'quantity'`

## Ajuste realizado

- Removido `**trade` das chamadas `diagnostics.info(...)` em `backend/app/backtest/strategies/strategy_runner.py`.
- Campos de diagnóstico agora são enviados explicitamente uma única vez:
  - `ticker`
  - `date`
  - `price`
  - `quantity`
  - `gross_value`
  - `transaction_cost`
  - `net_value`
  - `cash_before`
  - `cash_after`
  - `delta`

## Escopo preservado

- Não altera seleção de ativos.
- Não altera `factor_score`.
- Não altera cálculo de compra/venda.
- Não altera banco ou schema.
- Apenas corrige duplicidade de keyword no logging.

## Validação esperada

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=3 --mode=research --weight-return=0.7 --weight-trend=0.3 --weight-risk=0 --weight-liquidity=0 --weight-dividend=0
python scripts/report_backtest.py
```

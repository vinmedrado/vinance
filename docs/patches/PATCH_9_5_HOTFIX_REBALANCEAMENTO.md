# PATCH 9.5 — Rebalanceamento completo (compra e venda)

## Objetivo
Corrigir o Backtest Engine para executar rebalanceamento real com vendas e compras.

## Correções

- Mantém seleção/scoring existentes.
- Mantém proteção contra lookahead e execução no próximo pregão disponível.
- Calcula, para cada ativo, `current_value`, `target_value` e `delta`.
- Executa vendas quando `delta < 0`.
- Executa compras quando `delta > 0`.
- Executa todas as vendas antes das compras.
- Compras usam caixa atualizado após vendas.
- Mantém posições entre rebalanceamentos.
- Adiciona logs detalhados de:
  - delta por ativo;
  - tipo de operação;
  - quantidade;
  - preço;
  - cash antes/depois;
  - motivo real de bloqueio.

## Arquivos alterados

- `backend/app/backtest/backtest_engine.py`
- `backend/app/backtest/portfolio_manager.py`

## Validação sugerida

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --top-n=3 --mode=research
```

Resultado esperado:

- `orders_executed > 0`
- `trades > 0`
- vendas ocorrendo quando posições ficam acima do target
- caixa oscilando entre rebalanceamentos
- portfolio rebalanceando corretamente

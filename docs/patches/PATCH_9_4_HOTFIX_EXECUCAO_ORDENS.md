# PATCH 9.4 — Hotfix Execução Real de Ordens no Backtest

Correção focada exclusivamente na execução de ordens do Backtest Engine.

## Correções

- Garante que o portfólio inicia com `cash = initial_capital`.
- Valida `initial_capital > 0`.
- Corrige position sizing:
  - `target_value_per_asset = equity / selected_count`
  - `quantity = floor(target_value / price)`
  - `buy_value = quantity * price`
- Ajusta quantidade quando a taxa de transação faria a ordem ultrapassar o caixa disponível.
- Bloqueia ordem apenas por motivo real:
  - preço inválido;
  - valor alvo inválido;
  - caixa insuficiente;
  - quantidade zero.
- Mantém posições entre rebalanceamentos.
- Adiciona logs detalhados:
  - quantity calculada;
  - buy_value;
  - total_cost;
  - cash_before;
  - cash_after;
  - motivo real de bloqueio.

## Validação esperada

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --top-n=3 --mode=research
```

Resultado esperado quando houver scores e preços:

- `orders_executed > 0`
- `trades > 0`
- `cash` reduzindo corretamente
- posições mantidas entre rebalanceamentos

## Escopo

Não altera:

- seleção de ativos;
- modo research;
- modo no_lookahead;
- schema do banco;
- engines de análise/otimização.

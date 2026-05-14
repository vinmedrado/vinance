# PATCH 14 — Diversificação de Seleção

Adiciona penalização dinâmica de frequência na estratégia `multi_factor`, sem alterar o cálculo base do score.

## Regra

`score_final = score_original - penalty`

Onde:

- `penalty = frequencia_recente * fator_penalidade`
- janela padrão: últimos 6 rebalanceamentos
- fator padrão: 3 pontos
- cooldown: se o ativo apareceu nos últimos 3 rebalanceamentos consecutivos, reduz o score já penalizado em 25%.

## Logs

Cada rebalanceamento mostra:

- score original
- penalidade aplicada
- score final
- frequência recente
- consecutivos
- cooldown aplicado

## Validação

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=5 --mode=research
```

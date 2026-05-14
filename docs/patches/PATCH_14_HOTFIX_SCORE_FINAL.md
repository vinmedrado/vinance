# PATCH 14 HOTFIX — Penalização dinâmica aplicada no ranking

Correção do PATCH 14 para garantir que a seleção do `multi_factor` use o score final pós-penalização.

## Ajustes

- Ranking agora ordena por `final_score`, não por `score_original`.
- Penalização padrão elevada para 10 pontos por frequência recente.
- Cooldown padrão ajustado para 30% após 3 seleções consecutivas.
- `final_score` é armazenado nos diagnósticos e usado na seleção.
- Logs agora incluem, por ativo:
  - `ticker`
  - `score_original`
  - `penalty`
  - `final_score`
  - `frequencia_recente`
  - `consecutivos`
  - `cooldown_aplicado`

## Validação

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=5 --mode=research
```

Esperado:

- `ranking_sort_key = final_score`
- `dynamic_ranked_candidates` preenchido
- mudança gradual dos ativos selecionados ao longo dos rebalanceamentos
- menor repetição de PETR4/B3SA3 quando a frequência recente aumentar

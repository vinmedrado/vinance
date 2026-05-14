# FinanceOS — PATCH 49: Motor de Score Final e Ranking por Mercado

Aplicado sobre PATCH 48.3.

## Objetivo
Criar motor de decisão final que combina:
- ML score
- Backtest score
- Risk score
- Data quality score

## Fórmula
score_final =
    (ml_score * 0.4) +
    (backtest_score * 0.3) +
    (risk_score * 0.2) +
    (data_quality_score * 0.1)

## Criado
- `services/final_ranking_service.py`

Funções:
- normalize_score(value, min_val, max_val)
- compute_ml_score(prediction)
- compute_backtest_score(backtest_data)
- compute_risk_score(asset_data)
- compute_final_score(asset)
- get_ranked_assets_by_market(market, limit, tenant_id)
- build_final_explanation(asset)
- get_market_leader(market, tenant_id)

## Atualizado
- `pages/19_Oportunidades_Mercado.py`

Agora mostra:
- melhor ativo do mercado
- Top 3
- Top 10
- componentes do score
- explicação simples
- classificação Forte / Boa / Neutra / Evitar

## Validação
Criado:
- `scripts/validate_final_ranking.py`

## Não implementado
- trades automáticos
- corretora
- ajuste automático de estratégia
- otimização dinâmica de pesos

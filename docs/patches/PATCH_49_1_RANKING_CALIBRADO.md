# FinanceOS — PATCH 49.1: Calibração Profissional do Ranking Final

Aplicado sobre PATCH 49.

## Melhorias no motor de ranking

### Normalização por mercado
- Criada `normalize_by_market(values, method="percentile")`
- Criada `robust_score(value, values, higher_is_better=True)`
- Usa comparação dentro do mesmo mercado/asset_class.

### Pesos configuráveis
- Criado `DEFAULT_FINAL_RANKING_WEIGHTS`
- `get_ranked_assets_by_market(..., weights=None)`
- Pesos são normalizados automaticamente.

### Risk score melhorado
risk_score =
- drawdown_score 45%
- volatility_score 35%
- stability_score 20%

Se risco não tiver dados:
- `risk_score = None`
- warning `missing_risk`

### Backtest score melhorado
backtest_score =
- return_score 40%
- winrate_score 20%
- drawdown_score 20%
- trade_count_score 10%
- consistency_score 10%

Se `total_trades < 10`:
- penaliza score em 30%
- warning `low_trade_count`

### Data completeness
Criado:
- `data_completeness_score`

Regras:
- 100 = todos componentes presentes
- 75 = falta 1
- 50 = faltam 2
- 25 = só 1 componente

Se completude < 75:
- classificação máxima = Neutra

Se qualidade baixa ou completude < 50:
- `eligible = false`
- `classification = Evitar`
- oculto por padrão no ranking

### Score breakdown e warnings
Cada ativo retorna:
- `score_breakdown`
- `warnings`
- `weights_used`
- `eligible`

Warnings:
- missing_ml
- missing_backtest
- missing_risk
- missing_quality
- low_quality_data
- low_trade_count
- high_drawdown

## UI atualizada
Arquivo:
- `pages/19_Oportunidades_Mercado.py`

Incluído:
- filtro mostrar/ocultar incompletos
- completude dos dados
- principais avisos
- explicação simples
- debug técnico para admin/analyst

## Teste
Criado:
- `scripts/test_final_ranking.py`

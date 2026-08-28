# FASE 26 — Vinance Recommendation Score Engine

## Objetivo

Unificar **Asset Score + Guardrails + Investor Profile + Trend/Momentum** em um `recommendation_score` final calculado em runtime no Budget Advisor.

A fase não cria tabela nova e não altera syncs, fundamentals, `asset_scores`, `asset_recommendation_guardrails` ou `asset_trend_signals`.

## Arquivos alterados/criados

- `backend/app/intelligence/services/recommendation_score_service.py`
- `backend/app/intelligence/services/budget_advisor_service.py`
- `backend/app/intelligence/schemas.py`
- `backend/tests/test_fase26_recommendation_score_engine.py`

## Service criado

`recommendation_score_service.py` expõe:

```python
calculate_recommendation_score(
    score_total,
    profile_score,
    status,
    risk_level,
    trend_label=None,
    momentum_score=None,
    trend_confidence=None,
    profile="MODERATE",
) -> Decimal
```

Também expõe `build_recommendation_components(...)` para explicar os componentes usados no cálculo retornado pelo Budget Advisor.

## Fórmula aplicada

### CONSERVATIVE

```text
recommendation_score =
  profile_score * 0.40
+ score_total * 0.25
+ momentum_score * 0.20
+ safety_score * 0.15
+ trend_adjustment
+ confidence_adjustment
```

### MODERATE

```text
recommendation_score =
  profile_score * 0.35
+ score_total * 0.30
+ momentum_score * 0.25
+ safety_score * 0.10
+ trend_adjustment
+ confidence_adjustment
```

### AGGRESSIVE

```text
recommendation_score =
  profile_score * 0.30
+ score_total * 0.35
+ momentum_score * 0.25
+ safety_score * 0.10
+ trend_adjustment
+ confidence_adjustment
```

## Safety Score

| Guardrail | Risk | safety_score |
|---|---:|---:|
| APPROVED | LOW | 100 |
| APPROVED | MEDIUM | 85 |
| WARNING | MEDIUM | 65 |
| WARNING | HIGH | 45 |
| BLOCKED | qualquer | 0 |

## Ajustes de tendência

| trend_label | ajuste |
|---|---:|
| UPTREND | +5 |
| SIDEWAYS | 0 |
| DOWNTREND | -8 |
| INSUFFICIENT_HISTORY | -3 |

## Ajustes de confiança

| confidence_level | ajuste |
|---|---:|
| HIGH | +3 |
| MEDIUM | +1 |
| LOW | -2 |
| VERY_LOW | -5 |
| null/ausente | -3 |

O resultado final é sempre limitado entre `0` e `100`.

## Integração com Budget Advisor

O endpoint existente continua o mesmo:

```text
GET /api/intelligence/budget-advisor
```

Agora o retorno inclui:

- `recommendation_score`
- `trend_label`
- `momentum_score`
- `trend_confidence`
- `trend_method`
- `recommendation_components_json`

A ordenação agora é feita por:

```text
recommendation_score desc, ticker asc
```

## Integração com trend_filter

O parâmetro `trend_filter` continua funcionando:

```text
GET /api/intelligence/budget-advisor?budget=150&market=FII&profile=CONSERVATIVE&trend_filter=UPTREND&limit=20
```

Fluxo:

1. Filtra tickers pela tendência solicitada.
2. Calcula `recommendation_score` para os ativos restantes.
3. Ordena por `recommendation_score desc`.

## Sem trend disponível

Se um ativo ainda não possuir registro em `asset_trend_signals`:

- `trend_label = null`
- `momentum_score = 0`
- `trend_confidence = VERY_LOW`
- recebe penalização via confidence adjustment.
- não quebra o Budget Advisor.

## Diversified Advisor

O endpoint diversificado também passa a usar o ranking do Budget Advisor com `recommendation_score`, mantendo as alocações por perfil da Fase 24.

```text
GET /api/intelligence/budget-advisor/diversified?budget=500&profile=CONSERVATIVE
```

## Testes adicionados

- `recommendation_score` sempre entre 0 e 100.
- `UPTREND` aumenta score.
- `DOWNTREND` reduz score.
- `HIGH` confidence melhora score.
- `LOW` confidence reduz score.
- `WARNING` reduz score via `safety_score`.
- Budget Advisor retorna campos de trend.
- Budget Advisor ordena por `recommendation_score desc`.
- Sem trend data não quebra.
- `trend_filter` continua filtrando corretamente.

## Validação

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Testar:

```text
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&profile=CONSERVATIVE&limit=20
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&profile=CONSERVATIVE&trend_filter=UPTREND&limit=20
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&profile=AGGRESSIVE&include_warnings=true&trend_filter=UPTREND&limit=20
```

Validar no JSON:

- `recommendation_score` aparece.
- `trend_label` aparece.
- `momentum_score` aparece.
- `trend_confidence` aparece.
- ordenação muda conforme tendência/momentum/confiança.

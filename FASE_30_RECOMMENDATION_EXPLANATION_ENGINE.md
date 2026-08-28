# FASE 30 — Vinance Recommendation Explanation Engine

## Objetivo

Adicionar uma camada derivada de explicação ao Budget Advisor para transformar a lista técnica de ativos em uma recomendação clara, com decisão principal, quantidade possível, uso do orçamento, motivos, sinal estimado de valorização e confiança.

## Escopo aplicado

Esta fase não altera syncs, schedules, fundamentals, `asset_scores`, guardrails, trends ou `recommendation_score`. A explicação é calculada em runtime, usando os dados que o Budget Advisor já retorna.

## Arquivos criados

- `backend/app/intelligence/services/recommendation_explanation_service.py`
- `backend/tests/test_fase30_recommendation_explanation_engine.py`
- `FASE_30_RECOMMENDATION_EXPLANATION_ENGINE.md`

## Arquivos alterados

- `backend/app/intelligence/services/budget_advisor_service.py`
- `backend/app/intelligence/router.py`

## Novo comportamento do Budget Advisor

O endpoint antigo continua funcionando normalmente quando `explain` não é enviado ou é `false`:

```text
GET /api/intelligence/budget-advisor?budget=300&market=FII&profile=CONSERVATIVE&limit=20
```

Quando `explain=true`, o retorno passa a ser um objeto explicativo:

```text
GET /api/intelligence/budget-advisor?budget=300&market=FII&profile=CONSERVATIVE&limit=20&explain=true
```

Formato principal:

```json
{
  "budget": "300.00",
  "market": "FII",
  "profile": "CONSERVATIVE",
  "best_recommendation": {
    "ticker": "CPTS11",
    "quantity_possible": 40,
    "invested_amount": "297.60",
    "remaining_budget": "2.40",
    "recommendation_title": "Melhor opção para seu perfil conservador",
    "decision_summary": "Com R$300.00, você consegue comprar 40 cota(s) de CPTS11, investindo aproximadamente R$297.60.",
    "why_recommended": [],
    "appreciation_signal": "MODERATE",
    "confidence_score": "83.00",
    "confidence_label": "HIGH",
    "disclaimer": "Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno."
  },
  "alternatives": []
}
```

## Endpoint opcional

Também foi adicionado:

```text
GET /api/intelligence/recommendation/explain?budget=300&market=FII&profile=CONSERVATIVE
```

Com `ticker` opcional:

```text
GET /api/intelligence/recommendation/explain?budget=300&market=FII&profile=CONSERVATIVE&ticker=CPTS11
```

Se `ticker` não for informado, o endpoint explica o melhor ativo. Se for informado, tenta explicar aquele ticker dentro das recomendações disponíveis.

## Sinal estimado de valorização

O campo `appreciation_signal` pode retornar:

- `HIGH`
- `MODERATE`
- `LOW`
- `UNKNOWN`

A lógica usa `recommendation_score`, `trend_label`, `momentum_score` e `trend_confidence`. O texto sempre usa linguagem cautelosa, como sinal, tendência atual e chance estimada. Não há promessa de lucro.

## Confiança da recomendação

O campo `confidence_score` fica entre 0 e 100 e considera:

- `recommendation_score`
- status dos guardrails
- `risk_level`
- `trend_confidence`

Labels:

- `HIGH` para score maior ou igual a 80
- `MEDIUM` para score maior ou igual a 60
- `LOW` abaixo de 60

## Segurança de linguagem

A camada evita termos como:

- garantido
- certeza de lucro

E inclui o disclaimer curto:

```text
Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno.
```

## Validação

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Testes manuais:

```text
http://localhost:8000/api/intelligence/budget-advisor?budget=300&market=FII&profile=CONSERVATIVE&limit=20&explain=true
http://localhost:8000/api/intelligence/budget-advisor?budget=300&market=FII&profile=AGGRESSIVE&include_warnings=true&limit=20&explain=true
```

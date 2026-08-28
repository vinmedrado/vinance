# FASE 23 — Vinance Recommendation Guardrails

## Objetivo

Adicionar uma camada derivada de proteção para recomendações do Vinance, evitando que ativos matematicamente baratos, com DY muito alto ou baixa liquidez sejam recomendados diretamente sem classificação de risco.

## O que foi criado

### Tabela `asset_recommendation_guardrails`

Campos implementados:

- `id`
- `ticker`
- `market`
- `date`
- `status`
- `risk_level`
- `penalty_score`
- `reasons_json`
- `calculated_at`
- `source`

Constraint única:

- `ticker + market + date + source`

Índices:

- `market + status + date`
- `ticker + market`

Migration:

- `backend/alembic/versions/0013_create_asset_recommendation_guardrails.py`

## Service criado

Arquivo:

- `backend/app/intelligence/services/recommendation_guardrail_service.py`

Responsabilidades:

- Buscar a última data disponível de `asset_scores` por mercado.
- Cruzar os scores com os fundamentals da mesma data.
- Classificar cada ativo como:
  - `APPROVED`
  - `WARNING`
  - `BLOCKED`
- Gerar `risk_level`:
  - `LOW`
  - `MEDIUM`
  - `HIGH`
- Gerar `penalty_score`.
- Registrar motivos estruturados em `reasons_json`.
- Fazer upsert em `asset_recommendation_guardrails`.

## Regras implementadas

### FIIs

`BLOCKED` se:

- `price <= 0`
- `score_total <= 0`
- `pvp <= 0`
- `dy_12m >= 30`
- `liquidez_diaria <= 50000`
- `num_cotistas <= 1000`

`WARNING` se:

- `dy_12m >= 18`
- `pvp < 0.50`
- `liquidez_diaria < 200000`
- `num_cotistas < 10000`
- `vacancia_fisica >= 20`

### Ações

`BLOCKED` se:

- `price <= 0`
- `score_total <= 0`
- `pl <= 0`
- `pvp <= 0`
- `roe <= 0`

`WARNING` se:

- `pl > 40`
- `pvp > 5`
- `dy_12m > 20`
- `roe < 5`
- `market_cap < 1B`, quando disponível
- `volume_medio_diario < 1M`, quando disponível

### ETFs

`BLOCKED` se:

- `price <= 0`
- `score_total <= 0`

`WARNING` se:

- `taxa_adm > 1.00`
- `volume_medio_diario < 200k`
- `patrimonio_liq < 100M`
- `retorno_12m < -20`

### BDRs

`BLOCKED` se:

- `price <= 0`
- `score_total <= 0`

`WARNING` se:

- `volume_medio_diario_brl < 200k`
- `market_cap < 10B`
- `dy_12m > 20`
- `pl <= 0`, quando disponível

## Task Celery criada

Task:

```python
market.calculate_recommendation_guardrails
```

Execução manual:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_recommendation_guardrails; calculate_recommendation_guardrails.delay(); print('guardrails enviados')"
```

## Budget Advisor ajustado

Arquivo:

- `backend/app/intelligence/services/budget_advisor_service.py`

Alterações:

- Por padrão, retorna apenas ativos `APPROVED`.
- Nunca retorna ativos `BLOCKED`.
- Aceita o parâmetro opcional `include_warnings=true`.
- Quando `include_warnings=true`, retorna `APPROVED + WARNING`.
- Resposta passa a incluir:
  - `status`
  - `risk_level`
  - `reasons_json`

Endpoint:

```http
GET /api/intelligence/budget-advisor?budget=150&market=FII&limit=20
GET /api/intelligence/budget-advisor?budget=150&market=FII&limit=20&include_warnings=true
```

## Endpoint novo

```http
GET /api/intelligence/guardrails?market=FII&status=WARNING&limit=50
```

Retorna:

- `ticker`
- `market`
- `date`
- `status`
- `risk_level`
- `penalty_score`
- `reasons_json`
- `source`

## Testes criados

Arquivo:

- `backend/tests/test_fase23_recommendation_guardrails.py`

Cobertura:

- HCTR11/DEVA11 caem em `WARNING` ou `BLOCKED` quando batem critérios.
- Preço zero vira `BLOCKED`.
- DY extremo vira `BLOCKED`.
- Budget Advisor não retorna `BLOCKED`.
- `include_warnings=true` retorna `APPROVED + WARNING`.
- `include_warnings=false` retorna apenas `APPROVED`.
- Constraint única da tabela de guardrails existe.

## Validação sugerida

```bash
docker compose build backend celery_worker celery_beat

docker compose run --rm backend alembic upgrade head

docker compose up -d --force-recreate backend celery_worker celery_beat
```

Rodar task:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_recommendation_guardrails; calculate_recommendation_guardrails.delay(); print('guardrails enviados')"
```

Validar banco:

```bash
docker compose exec postgres psql -U vinance -d vinance -c "select market, status, count(*) from asset_recommendation_guardrails group by market, status order by market, status;"
```

Testar endpoints:

```http
http://localhost:8000/api/intelligence/guardrails?market=FII&status=WARNING&limit=50
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&limit=20
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&limit=20&include_warnings=true
```

## Restrições respeitadas

- Syncs não alterados.
- CoinGecko não alterado.
- Investidor10 não alterado.
- Fundamentals não alterados.
- `asset_scores` não alterado.
- Frontend não alterado.
- Budget Advisor mantido e apenas filtrado por camada derivada de guardrails.

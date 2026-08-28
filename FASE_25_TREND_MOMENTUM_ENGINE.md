# FASE 25 — Vinance Trend & Momentum Engine

## Objetivo

Implementar uma camada derivada de tendência e momentum para FIIs, Ações, ETFs e BDRs, sem alterar syncs, provedores, fundamentals, `asset_scores`, guardrails, Budget Advisor ou Investor Profile Advisor.

## Hotfix — histórico curto

Este documento já contempla o hotfix da Fase 25 para melhorar o comportamento do Trend Engine quando o banco ainda possui poucos dias de histórico.

O hotfix mantém:

- tabela `asset_trend_signals`;
- task `market.calculate_trend_signals`;
- endpoint `/api/intelligence/trends`;
- parâmetro `trend_filter` no Budget Advisor;
- arquitetura derivada, sem alteração de coleta.

## Entregas

### 1. Tabela `asset_trend_signals`

Criada via migration Alembic:

- `backend/alembic/versions/0014_create_asset_trend_signals.py`

Campos:

- `id`
- `ticker`
- `market`
- `date`
- `price`
- `return_1d`
- `return_7d`
- `return_30d`
- `return_90d`
- `return_180d`
- `return_365d`
- `volatility_30d`
- `momentum_score`
- `trend_label`
- `risk_label`
- `metadata_json`
- `calculated_at`
- `source`

Constraint única:

- `ticker + market + date + source`

Índices:

- `market + trend_label + date`
- `market + risk_label + date`
- `ticker + market`

### 2. Service de tendência

Arquivo:

- `backend/app/intelligence/services/trend_signal_service.py`

Responsabilidades:

- Buscar histórico de preço das tabelas fundamentals existentes.
- Agrupar por ticker/data.
- Calcular retornos aproximados por horizonte.
- Calcular volatilidade com os registros disponíveis.
- Calcular `momentum_score` adaptativo entre 0 e 100.
- Classificar `trend_label`.
- Classificar `risk_label`.
- Preencher metadados de confiança.
- Fazer upsert em `asset_trend_signals`.
- Listar trends para endpoint.
- Fornecer conjunto de tickers para uso opcional no Budget Advisor.

## Regras adaptativas do hotfix

### Confidence level

O `metadata_json` agora contém:

- `observations_count`
- `trend_method`
- `confidence_level`

Valores de `confidence_level`:

- `HIGH`: 30 ou mais observações válidas.
- `MEDIUM`: 7 a 29 observações válidas.
- `LOW`: 3 a 6 observações válidas.
- `VERY_LOW`: menos de 3 observações válidas.

### Trend method

Valores de `trend_method`:

- `ADAPTIVE_30D`: 30 ou mais observações.
- `ADAPTIVE_7D`: 7 a 29 observações.
- `ADAPTIVE_SHORT`: 3 a 6 observações.
- `INSUFFICIENT_HISTORY`: menos de 3 observações.

### Trend Label

- Com `>= 30` observações: usa `return_7d` + `return_30d`.
- Com `>= 7` e `< 30` observações: usa `return_1d` + `return_7d`.
- Com `>= 3` e `< 7` observações: usa retorno acumulado curto + consistência de direção.
- Com `< 3` observações: retorna `INSUFFICIENT_HISTORY`.

Labels possíveis:

- `UPTREND`
- `SIDEWAYS`
- `DOWNTREND`
- `INSUFFICIENT_HISTORY`

Mesmo com histórico curto, o engine pode retornar `UPTREND` ou `DOWNTREND` quando a confiança for `LOW` ou `MEDIUM`. Essa limitação fica registrada no `metadata_json`.

### Momentum Score adaptativo

- Com `>= 30` observações: considera `return_7d`, `return_30d`, `return_90d` e `volatility_30d`.
- Com `>= 7` observações: considera `return_1d`, `return_7d` e volatilidade curta quando disponível.
- Com `>= 3` observações: considera retorno acumulado curto e consistência de direção.
- Com `< 3` observações: reduz confiança e limita o score.

### Retornos

- `return_1d`: preço atual contra preço anterior disponível.
- `return_7d`: preço atual contra preço disponível em até 7 dias atrás ou fallback por observações quando o histórico ainda é curto.
- `return_30d`: preço atual contra preço disponível em até 30 dias atrás ou fallback por observações quando houver pelo menos 30 observações.
- `return_90d`, `return_180d`, `return_365d`: calculados quando houver histórico suficiente.

Quando não há histórico suficiente, o campo fica `null` e o cálculo não quebra.

### Risk Label

- `LOW`: volatilidade até 1.5.
- `MEDIUM`: volatilidade até 3.5.
- `HIGH`: volatilidade acima de 3.5.
- `UNKNOWN`: sem volatilidade calculável.

Com histórico curto, o risk label pode usar volatilidade curta para evitar excesso de `UNKNOWN`.

## Endpoint de trends

Endpoint:

```http
GET /api/intelligence/trends?market=FII&trend=UPTREND&limit=50
```

Retorno principal:

- `ticker`
- `market`
- `date`
- `price`
- `return_1d`
- `return_7d`
- `return_30d`
- `return_90d`
- `volatility_30d`
- `momentum_score`
- `trend_label`
- `risk_label`
- `metadata_json`

Campos adaptativos disponíveis dentro de `metadata_json`:

- `observations_count`
- `trend_method`
- `confidence_level`
- `short_return`
- `short_volatility`
- `direction_consistency`

## Integração opcional no Budget Advisor

O Budget Advisor continua funcionando igual sem `trend_filter`.

Novo parâmetro opcional:

```http
trend_filter=UPTREND
```

Exemplo:

```http
GET /api/intelligence/budget-advisor?budget=150&market=FII&profile=CONSERVATIVE&trend_filter=UPTREND
```

Regra aplicada:

- Se `trend_filter` for informado, filtra apenas tickers cujo `trend_label` mais recente seja igual ao filtro.
- Aceita `UPTREND` mesmo com `confidence_level` `LOW` ou `MEDIUM`.
- Não há filtro automático por confiança nesta fase.
- Se `trend_filter` não for informado, o comportamento anterior não muda.

## Task Celery

Adicionada em:

- `backend/app/market/tasks.py`

Task:

```python
market.calculate_trend_signals
```

Uso manual:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_trend_signals; calculate_trend_signals.delay(); print('trend signals enviados')"
```

## Testes

Arquivo:

- `backend/tests/test_fase25_trend_momentum_engine.py`

Cobertura:

- 2 observações retornam `INSUFFICIENT_HISTORY`.
- 3 observações retornam tendência curta com `confidence_level=LOW`.
- 7 observações usam método `ADAPTIVE_7D` com `confidence_level=MEDIUM`.
- 30 observações usam método `ADAPTIVE_30D` com `confidence_level=HIGH`.
- `metadata_json` contém `observations_count`, `trend_method` e `confidence_level`.
- `Budget Advisor` sem `trend_filter` continua igual.
- `Budget Advisor` com `trend_filter` filtra corretamente.

## Validação recomendada

```bash
docker compose build backend celery_worker celery_beat
docker compose run --rm backend alembic upgrade head
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Rodar task manual:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_trend_signals; calculate_trend_signals.delay(); print('trend signals enviados')"
```

Validar banco:

```bash
docker compose exec postgres psql -U vinance -d vinance -c "select market, trend_label, risk_label, count(*) from asset_trend_signals group by market, trend_label, risk_label order by market, trend_label, risk_label;"
```

Testar endpoints:

```http
http://localhost:8000/api/intelligence/trends?market=FII&limit=20
```

```http
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&profile=CONSERVATIVE&trend_filter=UPTREND
```

## Arquivos alterados/criados

Criados na Fase 25:

- `backend/app/intelligence/asset_trend_signal_model.py`
- `backend/app/intelligence/services/trend_signal_service.py`
- `backend/alembic/versions/0014_create_asset_trend_signals.py`
- `backend/tests/test_fase25_trend_momentum_engine.py`
- `FASE_25_TREND_MOMENTUM_ENGINE.md`

Alterados na Fase 25:

- `backend/app/market/tasks.py`
- `backend/app/intelligence/router.py`
- `backend/app/intelligence/schemas.py`
- `backend/app/intelligence/services/budget_advisor_service.py`

Alterados no hotfix:

- `backend/app/intelligence/services/trend_signal_service.py`
- `backend/tests/test_fase25_trend_momentum_engine.py`
- `FASE_25_TREND_MOMENTUM_ENGINE.md`

## Garantias

- Não altera syncs.
- Não altera CoinGecko.
- Não altera Investidor10.
- Não altera fundamentals.
- Não altera `asset_scores`.
- Não altera `asset_recommendation_guardrails`.
- Não quebra Budget Advisor.
- Não quebra Investor Profile Advisor.
- Integração no Budget Advisor permanece opcional via `trend_filter`.

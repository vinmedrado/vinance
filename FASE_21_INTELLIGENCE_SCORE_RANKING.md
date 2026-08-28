# FASE 21 — Vinance Intelligence: Score e Ranking de Ativos

## Objetivo

Implementar a primeira camada derivada de inteligência do Vinance para scoring e ranking de FIIs, ações, ETFs e BDRs, sem alterar coleta, syncs, CoinGecko, Investidor10, fundamentals existentes ou frontend.

## Entregas realizadas

- Criada tabela derivada `asset_scores`.
- Criado model SQLAlchemy `AssetScore`.
- Criada migration Alembic `0011_create_asset_scores.py`.
- Criado service `backend/app/intelligence/services/asset_score_service.py`.
- Criada task Celery `market.calculate_asset_scores`.
- Criado endpoint `GET /api/intelligence/rankings?market=FII&limit=20`.
- Mantida compatibilidade com `/api/v1/intelligence/rankings`.
- Criados testes unitários e de endpoint em `backend/tests/test_fase21_asset_scores.py`.

## Tabela `asset_scores`

Campos principais:

- `ticker`
- `market`
- `date`
- `score_total`
- `score_value`
- `score_quality`
- `score_dividend`
- `score_liquidity`
- `score_risk`
- `price`
- `metadata_json`
- `calculated_at`
- `source`

Restrição única:

```sql
UNIQUE (ticker, market, date, source)
```

## Mercados suportados

- `FII`
- `ACOES`
- `ETF`
- `BDR`

## Regras iniciais de score

### FIIs

- `pvp`: menor é melhor
- `dy_12m`: maior é melhor
- `liquidez_diaria`: maior é melhor
- `num_cotistas`: maior é melhor
- `vacancia_fisica`: menor é melhor

### Ações

- `pl`: menor é melhor, ignorando negativos e nulos
- `pvp`: menor é melhor
- `roe`: maior é melhor
- `roic`: maior é melhor
- `dy_12m`: maior é melhor
- `market_cap`: maior é melhor
- `volume_medio_diario`: maior é melhor

### ETFs

- `taxa_adm`: menor é melhor
- `retorno_12m`: maior é melhor
- `patrimonio_liq`: maior é melhor
- `volume_medio_diario`: maior é melhor
- `num_cotistas`: maior é melhor

### BDRs

- `pl`: menor é melhor, ignorando negativos e nulos
- `pvp`: menor é melhor
- `dy_12m`: maior é melhor
- `market_cap`: maior é melhor
- `volume_medio_diario_brl`: maior é melhor

## Normalização

A normalização usa ranking percentil dentro do próprio mercado e da última data disponível de fundamentals.

O score final fica entre 0 e 100.

Campos nulos não quebram o cálculo e não zeram o ativo inteiro. Eles reduzem a cobertura/confiança registrada em `metadata_json`.

## Execução manual

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_asset_scores; calculate_asset_scores.delay(); print('scores enviados')"
```

## Validação SQL

```bash
docker compose exec postgres psql -U vinance -d vinance -c "select market, date, count(*) from asset_scores group by market, date order by market, date;"
```

## Endpoint

```http
GET http://localhost:8000/api/intelligence/rankings?market=FII&limit=20
```

Retorna ranking ordenado por `score_total desc`.

## Garantias da fase

- Não altera syncs.
- Não altera CoinGecko.
- Não altera Investidor10.
- Não altera Celery Beat existente.
- Não altera tabelas fundamentals existentes.
- Não altera frontend.

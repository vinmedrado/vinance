# FASE 22 — Vinance Budget Advisor

## Objetivo

Criar uma camada derivada de recomendação por orçamento usando a tabela `asset_scores`, sem alterar coletas, providers, syncs, CoinGecko, Investidor10, scoring existente ou frontend.

## Entregas implementadas

- Nova tabela `investment_recommendations`.
- Migration Alembic `0012_create_investment_recommendations.py`.
- Modelo SQLAlchemy `InvestmentRecommendation`.
- Service isolado `backend/app/intelligence/services/budget_advisor_service.py`.
- Endpoint simples `GET /api/intelligence/budget-advisor`.
- Endpoint diversificado `GET /api/intelligence/budget-advisor/diversified`.
- Testes unitários em `backend/tests/test_fase22_budget_advisor.py`.

## Regras aplicadas

### Budget Advisor por mercado

Entrada principal:

- `budget`
- `market`
- `limit`

Filtros:

- `price > 0`
- `score_total > 0`

Cálculo:

- `quantity_possible = floor(budget / price)`
- `invested_amount = price * quantity_possible`

Retorno apenas ativos com:

- `quantity_possible >= 1`

Ordenação:

- `score_total DESC`
- `ticker ASC` como critério estável de desempate

### Carteira diversificada

Endpoint:

```text
GET /api/intelligence/budget-advisor/diversified?budget=500
```

Alocação inicial:

- 40% FIIs
- 30% Ações
- 20% ETFs
- 10% BDRs

A regra usa o melhor ativo comprável de cada mercado conforme maior `score_total` disponível.

## Persistência

O endpoint simples persiste recomendações geradas na tabela `investment_recommendations`, registrando:

- orçamento usado
- mercado
- ticker
- score
- preço
- quantidade possível
- valor investido
- rank da recomendação
- data/hora de geração

O endpoint diversificado retorna a carteira simples de forma derivada e não duplica snapshots individuais por mercado.

## Validação sugerida

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Aplicar migrations:

```bash
docker compose run --rm backend alembic upgrade head
```

Testar endpoints:

```text
http://localhost:8000/api/intelligence/budget-advisor?budget=150&market=FII&limit=20
http://localhost:8000/api/intelligence/budget-advisor/diversified?budget=500
```

Validar tabela:

```bash
docker compose exec postgres psql -U vinance -d vinance -c "select budget, market, count(*) from investment_recommendations group by budget, market order by market;"
```

## Garantias da fase

- Não altera syncs.
- Não altera CoinGecko.
- Não altera Investidor10.
- Não altera `asset_scores`.
- Não altera frontend.
- Não altera tabelas de fundamentals.
- Usa somente camada derivada baseada em scores já calculados.

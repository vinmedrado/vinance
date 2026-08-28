# FASE 27 — Vinance Intelligence Scheduler

## Objetivo

Agendar automaticamente as camadas derivadas de inteligência do Vinance após o sync diário do Investidor10, mantendo a coleta e as tabelas existentes intactas.

## Escopo aplicado

Esta fase altera apenas a configuração do Celery Beat em:

- `backend/app/core/celery.py`

Não foram criadas tabelas novas, migrations, syncs, endpoints ou alterações no frontend.

## Pipeline diário configurado

O pipeline diário passa a executar na seguinte ordem:

| Horário | Task | Finalidade |
|---|---|---|
| 21:00 | `market.sync_all_investidor10` | Atualiza fundamentals via Investidor10 |
| 21:35 | `market.calculate_asset_scores` | Recalcula scores/rankings derivados |
| 21:45 | `market.calculate_recommendation_guardrails` | Recalcula guardrails de recomendação |
| 21:55 | `market.calculate_trend_signals` | Recalcula tendência e momentum |

## Schedules adicionados

Foram adicionadas ao `beat_schedule` as entradas:

- `market-calculate-asset-scores-daily-after-investidor10`
- `market-calculate-recommendation-guardrails-daily-after-scores`
- `market-calculate-trend-signals-daily-after-guardrails`

## Fila

As tasks derivadas de inteligência foram mantidas na fila:

- `intelligence`

As rotas explícitas adicionadas foram:

- `market.calculate_asset_scores` → `intelligence`
- `market.calculate_recommendation_guardrails` → `intelligence`
- `market.calculate_trend_signals` → `intelligence`

## O que não foi alterado

- Syncs existentes
- CoinGecko
- Investidor10
- Fundamentals
- `asset_scores`
- `asset_recommendation_guardrails`
- `asset_trend_signals`
- Budget Advisor
- Recommendation Score Engine
- Periodicidade de cripto
- Migrations
- Tabelas
- Frontend

## Validação sugerida

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Conferir schedule:

```bash
docker compose exec backend python -c "from backend.app.core.celery import celery_app; import pprint; pprint.pp(celery_app.conf.beat_schedule)"
```

Devem aparecer:

- `market-calculate-asset-scores-daily-after-investidor10`
- `market-calculate-recommendation-guardrails-daily-after-scores`
- `market-calculate-trend-signals-daily-after-guardrails`

Teste manual opcional:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import calculate_asset_scores, calculate_recommendation_guardrails, calculate_trend_signals; calculate_asset_scores.delay(); calculate_recommendation_guardrails.delay(); calculate_trend_signals.delay(); print('intelligence pipeline enviado')"
```

## Resultado esperado

Após o sync diário do Investidor10, o Vinance passa a recalcular automaticamente as camadas derivadas de inteligência. Com isso, o Budget Advisor e o Recommendation Score Engine passam a consumir dados atualizados sem execução manual diária.

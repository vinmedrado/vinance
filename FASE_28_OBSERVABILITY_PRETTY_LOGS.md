# FASE 28 — Vinance Observability & Pretty Logs

## Objetivo

Melhorar a visualização operacional dos logs do Vinance no terminal, permitindo acompanhar as rotinas principais em tempo real com resumos executivos, sem alterar regras de negócio, banco, schedules ou syncs.

## Escopo aplicado

Foi criada uma camada leve de logs visuais em:

- `backend/app/core/pretty_logs.py`

E aplicada somente em:

- `backend/app/market/tasks.py`

Nas tasks:

- `sync_cripto_coingecko`
- `sync_all_investidor10`
- `calculate_asset_scores`
- `calculate_recommendation_guardrails`
- `calculate_trend_signals`

## O que não foi alterado

- Syncs existentes
- Schedules do Celery Beat
- Banco de dados
- Migrations
- Regras de score
- Guardrails
- Trend Engine
- Recommendation Engine
- Logging global em `backend/app/core/logging.py`

## Helper criado

Arquivo:

```text
backend/app/core/pretty_logs.py
```

Funções disponíveis:

```python
log_task_start(logger, title, **payload)
log_task_success(logger, title, **payload)
log_task_warning(logger, title, **payload)
log_task_error(logger, title, **payload)
log_section(logger, title, lines)
```

## Exemplos de saída esperada

### CoinGecko

```text
🚀 [CRIPTO] Iniciando CoinGecko Sync
   Fonte: CoinGecko
   Total Estimado: 1000
   Páginas: 4
   Per Page: 250
   Moeda: brl
```

```text
✅ [CRIPTO] CoinGecko Sync finalizado
   Status: SUCCESS
   Total: 1000
   OK: 1000
   Erros: 0
   Sucesso: 100.0%
   Tempo: 2.94s
```

### Intelligence

```text
✅ 🧠 [INTELLIGENCE] Asset Scores finalizado
   Status: SUCCESS
   Salvos: X
   Tempo: 1.20s
```

### Guardrails

```text
✅ 🛡️ [GUARDRAILS] Regras de recomendação finalizadas
   Status: SUCCESS
   Approved: X
   Warning: Y
   Blocked: Z
   Salvos: N
   Tempo: 1.40s
```

### Trend Signals

```text
✅ 📈 [TREND] Trend Signals finalizado
   Status: SUCCESS
   Uptrend: X
   Sideways: Y
   Downtrend: Z
   Insufficient History: W
   Salvos: N
   Tempo: 1.80s
```

## Logs técnicos preservados

Os logs técnicos existentes, como:

- `market_task.sync_cripto_coingecko.started`
- `market_task.sync_cripto_coingecko.finished`
- `market_task.sync_all_investidor10.started`
- `market_task.sync_all_investidor10.finished`
- `market_task.calculate_asset_scores.finished`
- `market_task.calculate_recommendation_guardrails.finished`
- `market_task.calculate_trend_signals.finished`

foram mantidos.

A Fase 28 apenas adiciona uma camada visual acima dos logs já existentes.

## Validação

Build:

```bash
docker compose build backend celery_worker celery_beat
```

Subir serviços:

```bash
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Teste manual:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import sync_cripto_coingecko; sync_cripto_coingecko.delay(); print('cripto enviado')"
```

Ver logs:

```bash
docker compose logs -f celery_worker
```

## Resultado

O terminal passa a exibir blocos visuais para acompanhar o Vinance trabalhando em tempo real, com leitura mais simples para operação, sem interferir na arquitetura, schedules ou regras financeiras.

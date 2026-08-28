# FASE 29 — Vinance Clean Runtime Logs

## Objetivo

Reduzir ruído operacional nos logs do terminal, mantendo visíveis os eventos importantes do Vinance em tempo real.

Esta fase não altera syncs, schedules, banco, migrations ou regras de negócio. O objetivo é apenas melhorar a leitura dos logs em runtime.

## Alterações realizadas

### 1. Redução de logs HTTP

Arquivo alterado:

- `backend/app/core/logging.py`
- `backend/app/core/celery.py`

Foram configurados os loggers abaixo para `WARNING`:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
```

Isso reduz mensagens repetitivas como:

- `HTTP Request: GET ...`
- logs internos de transporte HTTP

Warnings e erros continuam visíveis.

### 2. Logs repetitivos do CoinGecko movidos para DEBUG

Arquivo alterado:

- `backend/app/market/providers/coingecko.py`

Os logs abaixo foram mantidos, mas rebaixados para `DEBUG`:

- `CoinGecko markets page request started`
- `CoinGecko markets page request finished`

Logs relevantes continuam em `WARNING`/`ERROR`, incluindo:

- rate limit `429`
- timeout
- transport error
- erro HTTP
- JSON inválido

### 3. Configuração mais limpa do Celery Worker

Arquivo alterado:

- `backend/app/core/celery.py`

Foram adicionadas configurações para reduzir ruído do worker sem esconder exceções:

```python
worker_hijack_root_logger = False
worker_redirect_stdouts = False
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"
```

### 4. Celery Worker executando sem root

Arquivo alterado:

- `docker-compose.yml`

O comando do `celery_worker` agora usa:

```bash
--uid=nobody
```

Também foi ajustado para `--loglevel=warning`, reduzindo mensagens operacionais automáticas do Celery, como logs de task finalizada com sucesso.

## O que continua visível

A Fase 29 mantém visíveis:

- 🚀 início das tasks via `pretty_logs`
- ✅ sucesso das tasks via `pretty_logs`
- ⚠️ warnings reais
- ❌ erros reais
- rate limit `429`
- timeouts
- exceptions

## O que fica menos ruidoso

Devem aparecer menos mensagens como:

- `HTTP Request: GET ...`
- `CoinGecko markets page request started`
- `CoinGecko markets page request finished`
- logs automáticos excessivos de task succeeded
- SecurityWarning de execução root do Celery Worker

## Validação recomendada

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Rodar manualmente:

```bash
docker compose exec backend python -c "from backend.app.market.tasks import sync_cripto_coingecko; sync_cripto_coingecko.delay(); print('cripto enviado')"
```

Acompanhar logs:

```bash
docker compose logs -f celery_worker
```

Resultado esperado:

```text
🚀 [CRIPTO] Iniciando CoinGecko Sync
✅ [CRIPTO] CoinGecko Sync finalizado
```

Sem excesso de logs por página e sem flood de `HTTP Request: GET ...`.

## Observação

Esta fase preserva os logs técnicos importantes. Apenas logs informacionais muito repetitivos foram reduzidos para deixar o terminal mais útil durante operação diária.

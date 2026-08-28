# Correção Celery Async Event Loop — Vinance v2

## Problema corrigido
Tasks Celery síncronas estavam executando corrotinas com `asyncio.run(...)`, o que podia reutilizar engine/pool async do SQLAlchemy/asyncpg entre loops/forks do worker e gerar:

- `got Future attached to a different loop`
- `Event loop is closed`

## Arquivos alterados

- `backend/app/core/celery_async.py`
- `backend/app/core/database.py`
- `backend/app/market/scheduler/tasks.py`
- `backend/app/intelligence/scheduler/tasks.py`

## Correção aplicada

- Criado helper `run_celery_coroutine(...)` para tasks Celery.
- Cada task passa a criar um event loop novo por execução.
- O loop é registrado com `asyncio.set_event_loop(loop)` somente durante a task.
- Ao final da execução, o helper chama `close_database_connections()` e fecha o loop.
- `close_database_connections()` usa `await engine.dispose()` para evitar reutilização de conexões async entre loops.
- Todas as sessões continuam sendo criadas dentro das corrotinas com `async with AsyncSessionLocal()`.

## Escopo preservado

Não foram alterados:

- regras de negócio;
- providers;
- migrations;
- frontend;
- advisor;
- lógica de mercado;
- lógica de intelligence.

## Validação executada

```bash
python -m compileall backend/app scripts workers
```

Resultado: OK.

## Validações operacionais recomendadas no ambiente Docker

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
celery call market.sync_crypto_market
celery call intelligence.compute_all_market_features
```

Verificar logs do `celery_worker` e confirmar ausência de:

- `attached to a different loop`
- `Event loop is closed`

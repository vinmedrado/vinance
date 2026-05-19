# Vinance — Production Readiness

Este pacote consolida o Vinance como uma base operacional para empresa: autenticação real, modo demo preservado, Quant Intelligence persistente, jobs assíncronos, Docker, Render blueprint e smoke test.

## Escopo entregue

- Backend FastAPI com health, ready, live e métricas básicas.
- Autenticação real com cadastro, login, refresh token, logout e `/auth/me`.
- Modo demo preservado para demonstração controlada.
- Multi-tenant base com organizations, memberships, roles, permissions e audit logs.
- Quant Intelligence com decisão de capital investível, alocação, backtest, treino de sinais e histórico persistido.
- Celery Worker/Beat para tarefas longas.
- Render blueprint com backend, frontend, worker, beat, Redis e Postgres.
- Smoke test de ponta a ponta em `scripts/smoke_vinance.py`.

## O que precisa ser configurado fora do código

- `SECRET_KEY` forte em produção.
- `DATABASE_URL` e `SYNC_DATABASE_URL` do Postgres.
- `REDIS_URL`, `CELERY_BROKER_URL` e `CELERY_RESULT_BACKEND`.
- `CORS_ORIGINS` com o domínio real do frontend.
- Opcional: `VINANCE_ENABLE_YFINANCE=true` para consulta externa via yfinance.

## Comandos de validação

```bash
docker compose build backend frontend worker beat
docker compose up -d
python scripts/smoke_vinance.py
```

## Política de dados de mercado

O Quant Lab funciona com universo interno persistido. Integração externa é opcional e segura: se provider externo falhar, o sistema continua operacional com fallback determinístico.

## Critério de pronto para deploy inicial

- `BACKEND IMPORT OK` passa.
- `/health` retorna 200.
- `/api/auth/login` retorna token.
- `/api/quant/investment-decision` persiste execução.
- `/api/quant/backtest/run` persiste backtest.
- Frontend abre e acessa `/api` via proxy ou `VITE_API_URL`.

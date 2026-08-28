# Vinance v2 — Deployment Operacional

Este documento resume a operação local/produção. Para deploy em Netlify/Railway, consulte também `DEPLOY_GUIDE.md`.

## Variáveis obrigatórias em produção

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://usuario:senha-forte@host:5432/vinance
REDIS_URL=redis://usuario:senha-forte@host:6379/0
CELERY_BROKER_URL=redis://usuario:senha-forte@host:6379/0
CELERY_RESULT_BACKEND=redis://usuario:senha-forte@host:6379/1
SECRET_KEY=<gerada-com-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
LOG_LEVEL=INFO
CORS_ORIGINS=https://seu-frontend.com
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Nunca use a `SECRET_KEY` dos exemplos. Em produção, o backend bloqueia chaves vazias, curtas ou com placeholders em inglês/português.

## Docker Compose local

```bash
cp .env.example .env
docker compose up --build
```

Serviços esperados:

- `backend`: API FastAPI.
- `postgres`: banco relacional.
- `redis`: cache, broker Celery e memória curta do Advisor.
- `celery_worker`: execução assíncrona.
- `celery_beat`: agendamentos.

## Migrations

```bash
docker compose exec backend alembic upgrade head
```

Antes de deploy real, valide se `DATABASE_URL` aponta para o banco correto.

## Healthcheck

```bash
curl http://localhost:8000/health
```

A resposta deve cobrir:

- `api`
- `database`
- `redis`

## Celery worker

```bash
celery -A backend.app.core.celery.celery_app worker --loglevel=info -Q default,market,intelligence
```

## Celery beat

```bash
celery -A backend.app.core.celery.celery_app beat --loglevel=info
```

## Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Cuidados com Redis/Postgres

- Use credenciais fortes em produção.
- Não use bancos locais ou dumps no GitHub.
- Configure backups para Postgres.
- Redis deve ser gerenciado ou persistente quando possível.

## Cuidados com Groq

- `GROQ_API_KEY` nunca deve ser versionada.
- Sem chave Groq, o Advisor retorna fallback controlado.
- A integração não usa streaming, tools ou function calling nesta fase.

## Checklist pré-deploy

```bash
python -m compileall backend/app scripts workers
cd frontend && npm install && npm run build
alembic upgrade head
curl http://localhost:8000/health
```

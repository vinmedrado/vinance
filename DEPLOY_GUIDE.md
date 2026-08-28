# Vinance v2 — Deploy Guide

Este guia prepara o Vinance v2 para deploy futuro com frontend no Netlify, backend no Railway, Postgres, Redis, Celery worker/beat e Groq.

## 1. Frontend no Netlify

Configuração sugerida:

- Base directory: `frontend`
- Build command: `npm run build`
- Publish directory: `frontend/dist`

Variáveis no Netlify:

```env
VITE_API_BASE_URL=https://sua-api.up.railway.app
VITE_API_PREFIX=/api/v1
```

Após publicar, adicione a URL do Netlify em `CORS_ORIGINS` no backend.

## 2. Backend no Railway

Crie um serviço a partir do repositório GitHub apontando para a raiz do projeto.

Comando de start sugerido:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

Variáveis obrigatórias:

```env
ENVIRONMENT=production
APP_NAME=Vinance v2
APP_VERSION=2.0.0
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/vinance
REDIS_URL=redis://usuario:senha@host:6379/0
CELERY_BROKER_URL=redis://usuario:senha@host:6379/0
CELERY_RESULT_BACKEND=redis://usuario:senha@host:6379/1
SECRET_KEY=<gerada-com-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=https://seu-site.netlify.app
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

## 3. Postgres

Use Postgres gerenciado no Railway ou outro provedor.

Cuidados:

- Não usar usuário/senha padrão dos exemplos.
- Rodar migrations antes de liberar tráfego.
- Validar backups e política de retenção.
- Confirmar que `DATABASE_URL` usa driver async compatível: `postgresql+asyncpg://...`.

## 4. Redis

Redis é usado para:

- Celery broker;
- Celery result backend;
- memória curta do Advisor IA.

Cuidados:

- Usar Redis gerenciado em produção.
- Configurar `REDIS_URL`, `CELERY_BROKER_URL` e `CELERY_RESULT_BACKEND`.
- Verificar política de persistência/expiração conforme o provedor.

## 5. Celery worker

Crie um serviço separado no Railway usando o mesmo repositório e variáveis do backend.

Comando:

```bash
celery -A backend.app.core.celery.celery_app worker --loglevel=info -Q default,market,intelligence
```

## 6. Celery beat

Crie outro serviço separado para agendamentos.

Comando:

```bash
celery -A backend.app.core.celery.celery_app beat --loglevel=info
```

## 7. Migrations em produção

Depois de configurar `DATABASE_URL`, rode:

```bash
alembic upgrade head
```

No Railway, isso pode ser executado via shell/one-off command do serviço backend.

## 8. Groq

`GROQ_API_KEY` é opcional para subir a aplicação, mas necessária para resposta real do Advisor IA.

Cuidados:

- Não versionar chave Groq.
- Configurar a chave somente no painel do provedor.
- Monitorar timeout, rate limit e erros 429/5xx.
- O Advisor atual não usa streaming, tools ou function calling.

## 9. SECRET_KEY

Nunca use a `SECRET_KEY` de `.env.example` ou `.env.production.example`.

Gere uma chave forte:

```bash
openssl rand -hex 32
```

Em produção, o backend bloqueia chaves:

- vazias;
- com menos de 32 caracteres;
- contendo `change-me`, `default`, `example`, `phase1`;
- contendo placeholders em português como `troque`, `chave-segura`, `mais-de-32`, `placeholder`.

## 10. Checklist rápido de deploy

```bash
python -m compileall backend/app scripts workers
cd frontend && npm install && npm run build
alembic upgrade head
curl https://sua-api/health
```

Depois valide no navegador:

- cadastro/login;
- dashboard;
- financeiro;
- mercado;
- inteligência;
- advisor.

## Correção Fase 14 — legado e dados locais

Antes do deploy, confirme que a pasta ativa `services/` não existe na raiz do projeto. O conteúdo legado foi movido para `_archived/fase14_legacy_services/services/` apenas para histórico técnico e não deve ser usado em produção.

Ollama não faz parte do Vinance v2 aprovado. O advisor atual usa integração isolada com Groq no backend oficial, configurada exclusivamente por variáveis de ambiente seguras.

Não envie planilhas locais para produção ou GitHub. Arquivos `data/input/*.xlsm`, `data/input/*.xlsx`, `data/imports/*.xlsm` e `data/imports/*.xlsx` devem permanecer fora do versionamento.

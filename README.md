# Vinance v2

Vinance v2 é uma plataforma de inteligência financeira pessoal para o mercado brasileiro. O produto combina diagnóstico financeiro, organização de receitas e despesas, fundamentos de mercado, alocação educacional por perfil, ranking heurístico de ativos e um Advisor IA com contexto do usuário.

O foco do projeto é demonstrar uma arquitetura fullstack: backend FastAPI modular, frontend React, integração real entre camadas, documentação operacional e preparação segura para GitHub/deploy.

## Visão do produto

O Vinance ajuda o usuário a entender sua situação financeira antes de falar sobre investimentos. A jornada atual permite:

- criar conta e autenticar com JWT;
- cadastrar perfil financeiro inicial;
- registrar receitas e despesas;
- gerar diagnóstico financeiro;
- visualizar capacidade de investimento e alertas;
- consultar dados de mercado e fundamentos cadastrados;
- receber sugestões educacionais por classe de ativo;
- conversar com um Advisor IA educacional usando Groq, sem promessa de lucro ou recomendação definitiva de compra.

## Stack

### Backend

- Python 3.11+
- FastAPI
- SQLAlchemy Async
- Alembic
- PostgreSQL
- Redis
- Celery + Celery Beat
- Pydantic Settings
- httpx async para Groq
- Pytest

### Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Axios
- Design system próprio
- Identidade visual dark, com base inicial para light theme

## Módulos implementados

- `backend/app/auth`: autenticação, JWT e usuário autenticado.
- `backend/app/financial`: perfil financeiro, receitas, despesas, orçamento e diagnóstico.
- `backend/app/catalog`: catálogo base de ativos.
- `backend/app/market`: indicadores e fundamentos disponíveis por mercado.
- `backend/app/intelligence`: alocação por perfil, restrições de risco, scoring heurístico e ranking educacional.
- `backend/app/advisor`: Advisor IA educacional com Groq, memória curta em Redis e proteção básica contra prompt injection.
- `frontend/src/design-system`: tokens visuais, tema, tipografia, espaçamentos, radius e sombras.
- `frontend/src/features`: domínios conectados ao backend real: auth, financial, market, intelligence e advisor.
- `frontend/src/pages`: telas funcionais com onboarding, estados vazios, loading, error e UX de demo.

## Arquitetura resumida

```text
frontend/ React + Vite + TanStack Query
    ↓ HTTP /api/v1
backend/app FastAPI modular
    ↓
PostgreSQL — dados transacionais e fundamentos
Redis — cache, Celery broker/result backend e memória curta do Advisor
Celery Worker/Beat — jobs assíncronos preparados
Groq API — geração controlada do Advisor IA
```

## Status atual do projeto

Fases 0 a 14 concluídas:

- Fase 0: saneamento arquitetural.
- Fase 1: core backend.
- Fase 2: módulo financeiro.
- Fase 3: catálogo de ativos.
- Fase 4: market data.
- Fase 5: fundamentos de mercado.
- Fase 6: intelligence base heurística.
- Fase 7: Advisor IA com Groq.
- Fase 8: limpeza técnica e hardening.
- Fase 9: frontend base e identidade visual.
- Fase 10: integração frontend/backend real.
- Fase 11: onboarding financeiro e estados vazios.
- Fase 12: refinamento funcional das páginas.
- Fase 13: polimento final para demo.
- Fase 14: preparação GitHub + deploy.

O Vinance v2 está preparado para publicação no GitHub e para deploy futuro. Ainda não é uma versão comercial final.

## Como rodar o backend localmente

1. Copie o exemplo de ambiente:

```bash
cp .env.example .env
```

2. Ajuste pelo menos:

```env
DATABASE_URL=postgresql+asyncpg://vinance:vinance-local-only@postgres:5432/vinance
REDIS_URL=redis://redis:6379/0
SECRET_KEY=gere-uma-chave-real-forte-com-openssl-rand-hex-32
GROQ_API_KEY=
```

3. Suba os serviços:

```bash
docker compose up --build
```

4. Rode as migrations:

```bash
docker compose exec backend alembic upgrade head
```

5. Valide o healthcheck:

```bash
curl http://localhost:8000/health
```

## Como rodar o frontend localmente

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Por padrão, o frontend espera o backend em:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PREFIX=/api/v1
```

## Celery worker e beat

Com Docker Compose:

```bash
docker compose up celery_worker celery_beat
```

Manual:

```bash
celery -A backend.app.core.celery.celery_app worker --loglevel=info -Q default,market,intelligence
celery -A backend.app.core.celery.celery_app beat --loglevel=info
```

## Variáveis de ambiente principais

Backend:

- `ENVIRONMENT`
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SECRET_KEY`
- `CORS_ORIGINS`
- `LOG_LEVEL`
- `GROQ_API_KEY`
- `GROQ_MODEL`

Frontend:

- `VITE_API_BASE_URL`
- `VITE_API_PREFIX`

## Endpoints principais

- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET/POST /api/v1/financial/...`
- `GET /api/v1/catalog/...`
- `GET /api/v1/market/...`
- `GET /api/v1/intelligence/recommendations`
- `POST /api/v1/advisor/chat`

## Limitações atuais

- O Advisor é educacional e não substitui consultoria financeira profissional.
- Não há recomendação definitiva de compra/venda.
- Não há embeddings, vector database, LangChain, CrewAI, AutoGen ou Ollama.
- Não há backtest, LSTM, Prophet ou ML treinado.
- O frontend ainda não possui CRUD financeiro avançado.
- O mercado ainda não possui screener avançado ou gráficos complexos.
- Observabilidade e CI/CD ainda devem ser evoluídos antes de produção real.

## Próximos passos sugeridos

- Deploy frontend no Netlify.
- Deploy backend no Railway.
- Provisionar Postgres e Redis gerenciados.
- Configurar migrations em produção.
- Criar pipeline CI/CD.
- Adicionar observabilidade, logs estruturados e alertas.
- Evoluir telas com screenshots reais para portfólio.

## Segurança

- Nunca versionar `.env` real.
- Nunca versionar `GROQ_API_KEY`.
- Nunca usar a `SECRET_KEY` dos exemplos em produção.
- Gere `SECRET_KEY` forte com `openssl rand -hex 32` ou equivalente.
- Em `ENVIRONMENT=production`, o backend bloqueia `SECRET_KEY` vazia, curta ou com marcadores inseguros em inglês/português.

## Correção Fase 14 — limpeza de legado e planilhas locais

A pasta `services/` da raiz foi arquivada em `_archived/fase14_legacy_services/services/` por conter código legado fora do backend oficial `backend/app`. Essa arquitetura antiga não faz parte do Vinance v2 aprovado e podia conter referências a Ollama e variáveis antigas como `OPENAI_API_KEY`.

O Vinance v2 aprovado utiliza o backend oficial em `backend/app` e o advisor IA isolado via Groq. Ollama não faz parte da arquitetura atual do Vinance v2.

Arquivos locais de planilha, como entradas financeiras ou importações B3 (`.xlsm`/`.xlsx`), não são versionados. As pastas `data/input/` e `data/imports/` permanecem apenas com `.gitkeep`.

## Licença

MIT.

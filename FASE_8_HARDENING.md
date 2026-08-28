# Fase 8 — Limpeza Técnica + Hardening

## Objetivo

Preparar o backend do Vinance v2 para uma base mais estável antes da construção do frontend, sem criar features novas e sem alterar comportamento de domínio já aprovado.

## Arquivos criados/atualizados

Criados/atualizados nesta fase:

- `README.md`
- `DEPLOYMENT.md`
- `FASE_8_HARDENING.md`
- `.env.example`
- `.gitignore`
- `backend/app/core/config.py`
- `backend/app/main.py`

## Limpeza de artefatos

Removidos do pacote:

- `.pytest_cache/`
- diretórios `__pycache__/`, quando existentes
- arquivos `*.pyc`, quando existentes
- arquivos temporários e logs locais, quando existentes

O `.gitignore` cobre:

- `__pycache__/`
- `.pytest_cache/`
- `*.pyc`
- `.env`
- `logs/`
- `.DS_Store`
- caches comuns de Python e frontend

## Revisão de imports

Foi feita busca no backend ativo por imports ou referências perigosas a:

- Ollama
- LangChain
- CrewAI
- AutoGen
- Streamlit legado
- frontend

Não foram encontrados imports ativos desses itens em `backend/`, `scripts/` ou `workers/`, exceto strings de teste que validam ausência de frameworks proibidos no Advisor.

## Ajustes de configuração

- `LOG_LEVEL` agora é normalizado para valores conhecidos.
- `CORS_ORIGINS` foi adicionado ao `.env.example` e ao `Settings`.
- `SECRET_KEY`, `DATABASE_URL` e `REDIS_URL` são validados de forma mais rígida em produção.
- `GROQ_API_KEY` permanece opcional em desenvolvimento.
- Nenhum segredo real foi adicionado ao projeto.

## Segurança leve

- CORS passou a ser configurável por variável de ambiente.
- `SECRET_KEY` padrão é bloqueado em ambiente de produção.
- O tratamento global de exceções mantém erro interno genérico sem vazar stack trace na resposta HTTP.
- Advisor mantém proteção básica contra prompt injection e instrução explícita para não revelar system prompt.
- Payload do Advisor já possui limite básico via schema.
- Endpoints privados seguem protegidos por dependência de autenticação.

## Healthcheck expandido

`GET /health` agora retorna:

- status geral
- `api`
- `database`
- `redis`

Database e Redis são verificados por conexão real; não foi criado health fake.

## Validação executada

Executado no sandbox:

```bash
python -m compileall backend/app scripts workers
```

Resultado: OK.

Limitações do sandbox:

- `pytest` não pôde ser executado porque o ambiente local do sandbox não possui as dependências do projeto instaladas, como `sqlalchemy`.
- `alembic upgrade head` não pôde ser executado pelo mesmo motivo/ausência do binário no ambiente.
- Startup real de backend, Celery worker e Celery beat depende de Docker/Postgres/Redis disponíveis.

Com dependências instaladas, validar em ambiente local com:

```bash
pip install -r requirements.txt
python -m compileall backend/app scripts workers
pytest
alembic upgrade head
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
celery -A backend.app.core.celery.celery_app worker --loglevel=info -Q default,market,intelligence
celery -A backend.app.core.celery.celery_app beat --loglevel=info
```

## Riscos remanescentes

- Necessário testar deploy real com Postgres e Redis vivos.
- Necessário validar CORS com o domínio real do frontend quando ele for criado.
- Necessário monitorar custos, timeout e rate limit do Groq em produção.
- Segurança de produção ainda exige gestão real de secrets, observabilidade e política de backup.

## O que fica preparado para a Fase 9

- Backend mais limpo para acoplar frontend sem carregar caches ou artefatos locais.
- Configuração mais clara para ambiente real.
- Documentação operacional mínima para rodar API, migrations e workers.
- Advisor, Intelligence, Market, Catalog e Financial preservados sem mudança de domínio.

## Correção adicional — SECRET_KEY em produção

Foi aplicado um hotfix na validação de configuração para bloquear, em `ENVIRONMENT=production`, qualquer `SECRET_KEY` vazia, com menos de 32 caracteres ou contendo marcadores inseguros como `change-me`, `default`, `example` ou `phase1`. A validação de produção também confirma que `DATABASE_URL` e `REDIS_URL` não estejam vazias. O `.env.example` e o `DEPLOYMENT.md` foram atualizados para reforçar que a chave de exemplo nunca deve ser usada em produção.

## Correção adicional — placeholders em português

Foi aplicada uma correção complementar na validação de produção da `SECRET_KEY`. Além dos bloqueios já existentes para valor vazio, tamanho inferior a 32 caracteres e marcadores `change-me`, `default`, `example` e `phase1`, agora também são bloqueados placeholders em português ou genéricos contendo `troque`, `chave-segura`, `mais-de-32` ou `placeholder`.

Essa correção impede que o valor demonstrativo `troque-por-uma-chave-segura-com-mais-de-32-caracteres` passe em `ENVIRONMENT=production`. Nenhum módulo de domínio foi alterado.

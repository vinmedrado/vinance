# Fase 1 — Core Backend

## Resultado

A Fase 1 consolidou uma fundação backend única para o Vinance v2, sem avançar para financeiro, market, ML, advisor IA ou frontend.

A raiz oficial passa a ser exclusivamente:

```text
backend/app/
```

## Arquivos criados

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/core/redis.py`
- `backend/app/core/celery.py`
- `backend/app/core/logging.py`
- `backend/app/core/errors.py`
- `backend/app/auth/models.py`
- `backend/app/auth/schemas.py`
- `backend/app/auth/security.py`
- `backend/app/auth/service.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/router.py`
- `backend/app/api/v1/router.py`
- `backend/app/models.py`
- `backend/alembic/versions/0001_create_users.py`
- `workers/celery_app.py`
- `backend/tests/__init__.py`
- `backend/tests/test_core_contracts.py`
- `.gitkeep` em diretórios reservados para fases futuras.

## Arquivos alterados

- `.env.example`
- `docker-compose.yml`
- `README.md`
- `requirements.txt`
- `alembic.ini`
- `backend/alembic/env.py`

## Arquivos arquivados

Foram movidos para `_archived/phase1_core_backend/` para eliminar duplicidade arquitetural sem apagar material útil:

- `app/` → `_archived/phase1_core_backend/root_app_legacy/`
- `alembic/` → `_archived/phase1_core_backend/root_alembic_legacy/`
- `backend/app/` legado → `_archived/phase1_core_backend/backend_app_legacy/`
- migrations antigas de `backend/alembic/versions/` → `_archived/phase1_core_backend/backend_alembic_versions_legacy/`
- `backend/tests/` legado → `_archived/phase1_core_backend/backend_tests_legacy/`

## Decisões arquiteturais

1. **Backend único**: `backend/app/` é a única raiz oficial. A antiga pasta `app/` de raiz foi arquivada.
2. **Configuração centralizada**: `backend/app/core/config.py` concentra APP, DATABASE, REDIS, CELERY, GROQ e SECURITY.
3. **Banco async**: SQLAlchemy async foi adotado desde a base para evitar refatoração estrutural futura.
4. **Redis único**: o cliente Redis fica centralizado em `backend/app/core/redis.py`, com healthcheck e retry básico.
5. **Celery central**: filas `default`, `market` e `intelligence` foram preparadas, mas sem tasks reais.
6. **Auth mínima**: foi criado apenas o necessário para autenticação: usuário, hash de senha, JWT, `/register`, `/login`, `/me`.
7. **Alembic limpo**: a árvore oficial de migrations foi reiniciada com uma única migration de `users`.
8. **Legado preservado**: nada crítico foi apagado; módulos antigos foram arquivados para consulta.

## Validações executadas neste pacote

- Compilação Python dos módulos de `backend/app` e `workers` concluída com sucesso via `python -m compileall`.
- Verificação de estrutura confirmou ausência de `app/` e `alembic/` na raiz oficial.
- Docker/Postgres/Redis não estão disponíveis no ambiente de geração do pacote; por isso, a validação runtime completa deve ser executada localmente.

## Validação manual obrigatória

Com Docker disponível, a validação esperada é:

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend alembic upgrade head
curl http://localhost:8000/health
```

Fluxo de auth:

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@vinance.local","password":"SenhaForte123","full_name":"Teste"}'

curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@vinance.local","password":"SenhaForte123"}'

curl http://localhost:8000/me \
  -H "Authorization: Bearer <TOKEN>"
```


## Correção de isolamento de testes da Fase 1

- A pasta `tests/` da raiz continha testes legados fora do escopo da Fase 1 e foi arquivada em `_archived/phase1_core_backend/root_tests_legacy/`.
- O arquivo `pytest.ini` foi ajustado para executar somente `backend/tests`.
- A validação automatizada da Fase 1 agora está isolada do legado e não executa testes antigos de financeiro, RBAC, multi-tenancy, advisor, market ou ML.

## Riscos remanescentes

- A validação completa depende de Docker/Postgres/Redis ativos.
- O frontend legado ainda existe, mas não foi ajustado para o backend novo.
- O legado arquivado ainda precisa ser revisado nas próximas fases antes de qualquer reaproveitamento.
- Migrations antigas foram preservadas, mas não devem ser executadas contra a árvore nova.

## Preparado para Fase 2

A Fase 2 pode iniciar o domínio financeiro com segurança porque agora existem:

- Configuração tipada.
- Banco async e sessão limpa.
- Redis central.
- Celery pronto para jobs futuros.
- Auth mínima funcional.
- Alembic sem conflito de árvores.
- Tratamento global de erro.
- Healthcheck real.

## Fora do escopo confirmado

Não foram criados:

- lógica financeira;
- providers externos;
- market data;
- scraping;
- ML;
- advisor IA;
- billing;
- RBAC complexo;
- multi-tenant;
- alterações de frontend.

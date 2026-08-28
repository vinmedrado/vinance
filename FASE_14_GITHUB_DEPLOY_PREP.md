# Fase 14 — Preparação GitHub + Deploy

## Objetivo

Preparar o Vinance v2 para publicação profissional no GitHub e deploy futuro, sem criação de features novas e sem alteração funcional de backend/frontend.

## Arquivos revisados

- `.gitignore`
- `.env.example`
- `.env.production.example`
- `frontend/.env.example`
- `README.md`
- `DEPLOYMENT.md`
- estrutura do frontend para remoção de build/caches
- estrutura do backend para remoção de caches/pyc

## Arquivos criados

- `DEPLOY_GUIDE.md`
- `GITHUB_PUBLICATION_CHECKLIST.md`
- `FASE_14_GITHUB_DEPLOY_PREP.md`

## Arquivos atualizados

- `README.md`: versão final para GitHub, com visão do produto, stack, arquitetura, execução local, status, limitações e próximos passos.
- `.gitignore`: cobertura reforçada para envs reais, node_modules, dist, pycache, pytest cache, logs, bancos locais, dumps, backups e tsbuildinfo.
- `.env.example`: exemplos seguros para backend, database, Redis, Celery, Groq, CORS, secret key e frontend.
- `.env.production.example`: exemplo seguro e alinhado ao Vinance v2.
- `frontend/.env.example`: variáveis Vite alinhadas com backend FastAPI.

## Revisão de sensíveis

Foram verificados padrões de risco para:

- `.env` real;
- chave Groq real;
- tokens JWT;
- dumps/bancos locais;
- arquivos `.db`, `.sqlite`, `.dump`, `.bak`;
- logs, caches e builds.

Nenhum secret real foi inserido. Os valores presentes nos exemplos são placeholders documentados e bloqueados em produção quando aplicável.

## Validações executadas

- `python -m compileall backend/app scripts workers`: OK.
- `npm install`: OK.
- `npm run build`: OK.

Após a validação, os artefatos gerados foram removidos do pacote final:

- `frontend/node_modules/`
- `frontend/dist/`
- `frontend/tsconfig.tsbuildinfo`
- caches Python/pytest/Vite
- logs locais

## Riscos remanescentes

- Deploy real ainda precisa configurar variáveis no provedor.
- Postgres e Redis devem ser gerenciados com credenciais fortes e backup.
- Groq deve ser configurado somente via painel do provedor.
- CI/CD ainda não foi criado.
- Observabilidade de produção ainda deve ser evoluída.
- Screenshots finais para portfólio devem ser capturados após subir o frontend.

## Instruções finais de publicação

1. Conferir `GITHUB_PUBLICATION_CHECKLIST.md`.
2. Criar repositório GitHub.
3. Subir o conteúdo do ZIP final sem gerar `dist` ou `node_modules`.
4. Configurar Netlify para `frontend/`.
5. Configurar Railway para backend, worker e beat.
6. Provisionar Postgres e Redis.
7. Rodar `alembic upgrade head` em produção.
8. Configurar `CORS_ORIGINS` com o domínio do frontend.
9. Testar `/health`, login, dashboard, financeiro, mercado, intelligence e advisor.

## Estado final

A Fase 14 deixa o Vinance v2 pronto para GitHub e preparado para deploy futuro, mantendo a base funcional aprovada nas fases anteriores e sem adicionar feature creep.

## Correção adicional da Fase 14 — bloqueios resolvidos

### Bloqueios corrigidos

1. A pasta raiz `services/` continha código legado ativo fora do backend oficial, incluindo referência a Ollama em `services/ai.py`.
2. O arquivo legado `services/agents/base_agent.py` continha uso de `OPENAI_API_KEY`, fora da arquitetura aprovada do Vinance v2.
3. Existiam planilhas locais potencialmente sensíveis em `data/input/financas.xlsm` e `data/imports/b3.xlsx`.

### Arquivos arquivados

- `services/` → `_archived/fase14_legacy_services/services/`

Motivo: manter histórico técnico sem deixar código legado no caminho ativo do projeto. O backend aprovado permanece exclusivamente em `backend/app`.

### Arquivos removidos

- `data/input/financas.xlsm`
- `data/imports/b3.xlsx`

As pastas foram preservadas com:

- `data/input/.gitkeep`
- `data/imports/.gitkeep`

### `.gitignore` reforçado

Foram adicionadas regras para impedir versionamento de entradas locais e planilhas:

- `data/input/*`
- `!data/input/.gitkeep`
- `data/imports/*`
- `!data/imports/.gitkeep`
- `*.xlsm`
- `*.xlsx`

### Validações executadas

- `python -m compileall backend/app scripts workers`
- `npm install`
- `npm run build`

### Resultado

O pacote corrigido não mantém `services/` como código ativo, não inclui planilhas locais sensíveis e mantém backend/frontend aprovados sem alteração funcional.

# FinanceOS — Production Ready v2 Final Patch

## Objetivo
Patch final incremental focado exclusivamente em correção de produção, deploy e GitHub público profissional.

## Correções aplicadas

### 1. Streamlit removido do produto principal
- `app.py` movido para `legacy_streamlit/app.py`.
- `app/main_streamlit.py` movido para `legacy_streamlit/main_streamlit.py`.
- `pages/` movido para `legacy_streamlit/pages/`.
- `legacy_streamlit/README.md` criado para documentar uso legado/admin.
- `docker-compose.yml` atualizado para executar o Streamlit apenas no profile opcional `admin`.
- README e docs principais atualizados para deixar React/Vite como frontend oficial.

### 2. Nginx/proxy corrigido
- `deploy/nginx/financeos.conf` revisado.
- Proxy mantido para `/api/`.
- Healthchecks preservados em `/health`, `/ready` e `/health/full`.
- Compatibilidade explícita adicionada para `/demo/`, `/analytics/` e `/billing/`.
- Frontend React continua servindo todas as demais rotas.

### 3. `.gitignore` corrigido
- `.env.example` e `.env.production.example` agora podem ser versionados.
- `.env`, `.env.production` e demais envs reais continuam bloqueados.
- `frontend/tsconfig.tsbuildinfo`, builds, caches e temporários adicionados ao ignore.

### 4. Estratégia de API frontend padronizada
- `VITE_API_URL=/api` em produção quando frontend e backend usam o mesmo domínio via Nginx.
- `frontend/src/services/api.ts` usa `/api` como default.
- Chamadas internas do frontend foram ajustadas para evitar `/api/api/...`.
- `frontend/src/lib/analytics.ts` usa o mesmo base path configurado.
- Backend expõe aliases SaaS sob `/api` para analytics, demo e billing.

### 5. Limpeza final
- Removido `frontend/tsconfig.tsbuildinfo`.
- Removidos caches Python e artefatos temporários.
- Nenhum `.env` real foi incluído.

## Validação executada

- `python -m compileall backend app legacy_streamlit services scripts`: OK.
- `npm run build`: não concluído porque o ambiente não tinha dependências instaladas e `npm install` não concluiu neste container sem instalação completa de pacotes.
- `docker compose config`: não executado porque Docker não está disponível no ambiente (`docker: command not found`).
- `docker compose -f docker-compose.production.yml config`: não executado pelo mesmo motivo.

## Como validar localmente

```bash
cd frontend
npm install
npm run build
```

```bash
python -m compileall backend app legacy_streamlit services scripts
```

```bash
docker compose config
docker compose -f docker-compose.production.yml config
```

## Deploy recomendado

Produção com mesmo domínio:

```env
VITE_API_URL=/api
```

Rodar produção Docker:

```bash
cp .env.production.example .env.production
# edite secrets reais
docker compose -f docker-compose.production.yml up --build -d
```

Admin Streamlit legado opcional/local:

```bash
streamlit run legacy_streamlit/app.py
```

ou:

```bash
docker compose --profile admin up admin_streamlit
```

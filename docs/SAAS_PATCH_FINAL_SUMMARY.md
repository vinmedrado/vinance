# Patch final SaaS/Produção

## Entregas

- `.env.example` e `.env.production.example` revisados.
- `docker-compose.production.yml` com PostgreSQL, Redis, backend, frontend e Nginx.
- Healthcheck `/health` e readiness `/ready`.
- CORS via variável de ambiente.
- Docs ocultos em produção.
- Sentry backend/frontend opcional.
- Analytics PostHog opcional com fallback para endpoint backend.
- Demo pública isolada em `/demo`.
- Billing ready com helpers de planos/features.
- SEO/Open Graph/favicon no frontend.
- Nginx SPA + cache básico.
- Scripts de deploy.

## Validação esperada

```bash
python -m compileall backend services db scripts
cd frontend && npm install && npm run build && npm run lint
cd .. && docker compose -f docker-compose.production.yml config
```

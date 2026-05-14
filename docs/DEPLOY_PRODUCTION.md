# FinanceOS — Deploy Production Ready

## Docker local / VPS

1. Copie `.env.production.example` para `.env.production`.
2. Troque `SECRET_KEY`, `POSTGRES_PASSWORD`, `CORS_ORIGINS`, URLs públicas, Sentry, PostHog e Stripe.
3. Execute:

```bash
./scripts/deploy/start_production.sh
```

Endpoints úteis:

- Frontend: `http://localhost`
- API health: `http://localhost/health`
- API readiness: `http://localhost/ready`
- Demo pública: `/demo`

## Render

- Backend: Web Service Python, comando `gunicorn backend.app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`.
- Frontend: Static Site com build `npm install && npm run build`, publish `dist`.
- Banco: Render PostgreSQL.
- Redis: Render Redis.
- Configure as variáveis de `.env.production.example` no painel.

## Railway

- Suba PostgreSQL e Redis como serviços separados.
- Backend com Dockerfile raiz ou comando Gunicorn acima.
- Frontend com Dockerfile de `frontend/` ou static build.
- Use `VITE_API_URL=/api` quando frontend e backend estiverem no mesmo domínio via Nginx. Use URL absoluta apenas quando a API estiver em domínio separado.

## Observabilidade

- Backend: `SENTRY_DSN_BACKEND`.
- Frontend: `VITE_SENTRY_DSN`.
- Analytics: `VITE_ANALYTICS_ENABLED=true`, `VITE_POSTHOG_KEY` e `VITE_POSTHOG_HOST`.

## Billing ready

Stripe está preparado por placeholders reais. Antes de vender:

- criar produtos Free/Pro/Premium no Stripe;
- preencher `STRIPE_PRICE_PRO` e `STRIPE_PRICE_PREMIUM`;
- configurar webhook `/billing/webhook`;
- testar checkout em modo sandbox.

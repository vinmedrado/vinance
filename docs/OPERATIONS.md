# Operations

Comandos recomendados:

```bash
python -m compileall .
pytest -q tests
alembic upgrade head
docker compose config
docker compose -f docker-compose.production.yml config
cd frontend && npm install && npm run build
```

Rotas operacionais:

- `/health`
- `/ready`
- `/live`
- `/metrics`

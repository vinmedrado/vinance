# Vinance — Patch Render Ready

Este patch estabiliza a base para deploy inicial no Render sem recriar o projeto.

## Alterações principais

- Corrigido conflito `backend/app/auth.py` vs pacote `backend/app/auth/`.
- Auth consolidado como pacote real com `router`, `dependencies`, `password` e `jwt_handler`.
- Login demo funcional em `/auth/login` e `/api/auth/login`.
- Compatibilidade para `demo-token` em rotas protegidas.
- Proxy Nginx mantido para `/api/`.
- Helpers operacionais endurecidos em `backend/app/api_operational/db.py`.
- Compatibilidade legada concentrada em `sqlite_repository.py`.
- Logo Vinance integrado ao frontend.
- `render.yaml` inicial criado para backend, frontend, Postgres e Redis.

## Login demo local

- E-mail: `demo@financeos.local`
- Senha: `financeos123`

## Validação rápida

```bash
docker compose build backend frontend
docker compose run --rm backend python -c "from backend.app.main import app; print('BACKEND IMPORT OK')"
docker compose up
```

Acesse:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/docs
- Health: http://localhost:8000/health

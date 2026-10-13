# Production Deployment Runbook

## Pré-requisitos

Host Linux limpo com:

- Docker Engine e Docker Compose plugin;
- espaço livre suficiente para duas gerações de imagens, banco e backup temporário;
- usuário operacional sem uso diário de `root`;
- diretório persistente protegido para secrets e backups locais;
- relógio/NTP correto.

Python e Node não são requisitos do host.

## 1. Obter a versão

Faça checkout de um commit/tag aprovado ou use imagens identificadas pelo SHA. Não implante a partir de arquivos não versionados.

```bash
git checkout <commit-aprovado>
export APP_COMMIT_SHA="$(git rev-parse HEAD)"
```

## 2. Preparar configuração

Copie `.env.production.example` para um arquivo local fora do Git e substitua todos os placeholders. Gere segredos com fonte criptograficamente segura.

Permissões recomendadas:

```bash
chmod 600 .env.production
chmod 600 /caminho/seguro/backup-passphrase
```

Itens obrigatórios:

- credenciais exclusivas PostgreSQL/Redis;
- `SECRET_KEY` forte;
- `TRUSTED_HOSTS` e `CORS_ORIGINS` do ambiente;
- `REGISTRATION_ENABLED=false` após criar as contas autorizadas;
- path do segredo de backup;
- versão/SHA da aplicação.

## 3. Construir

```bash
docker compose --env-file .env.production -f docker-compose.production.yml build \
  --build-arg APP_COMMIT_SHA="$APP_COMMIT_SHA"
```

Inspecione o bundle dentro da imagem antes de publicar (um checkout limpo não possui `frontend/dist` no host):

```bash
FRONTEND_IMAGE="$(docker compose --env-file .env.production -f docker-compose.production.yml images -q frontend)"
docker run --rm --entrypoint sh "$FRONTEND_IMAGE" -c \
  "! grep -R -E 'localhost:8000|127\\.0\\.0\\.1:8000|192\\.168\\.' /usr/share/nginx/html"
```

## 4. Migrar e iniciar

O serviço one-shot de migration precede os serviços da aplicação.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Não execute Alembic simultaneamente em backend, Worker e Beat.

## 5. Verificar

```bash
EDGE_PORT="$(docker compose --env-file .env.production -f docker-compose.production.yml port frontend 8080 | sed 's/.*://')"
PUBLIC_HOST="$(docker compose --env-file .env.production -f docker-compose.production.yml exec -T backend printenv TRUSTED_HOSTS | cut -d, -f1)"
curl --fail -H "Host: $PUBLIC_HOST" "http://127.0.0.1:$EDGE_PORT/health"
curl --fail -H "Host: $PUBLIC_HOST" "http://127.0.0.1:$EDGE_PORT/ready"
docker compose --env-file .env.production -f docker-compose.production.yml exec celery_worker \
  celery -A backend.app.core.celery.celery_app inspect ping
```

Valide também:

- `/login`, `/financial`, `/investir` via edge;
- chamadas do browser somente para `/api/v1`;
- PostgreSQL, Redis e backend sem portas públicas;
- uma única réplica Beat;
- revision Alembic no head esperado.

## 6. Bootstrap privado

Habilite cadastro somente durante a criação controlada das contas autorizadas, ou utilize o procedimento administrativo documentado. Depois, defina `REGISTRATION_ENABLED=false` e recrie/reinicie backend e frontend conforme a configuração.

## 7. Backup inicial

Execute backup antes da primeira carga real e após cada migration relevante. Verifique exit code, tamanho, checksum e artefato cifrado. Mova uma cópia cifrada para armazenamento fora do host na Fase F.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml \
  --profile ops run --rm backup
```

Para um drill, crie antes um PostgreSQL isolado e vazio e forneça sua URL somente por ambiente; a senha não deve aparecer como argumento do processo:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml \
  --profile ops run --rm -e DRILL_TARGET_DATABASE_URL="$DRILL_TARGET_DATABASE_URL" \
  backup /usr/local/bin/drill.sh
```

Os volumes `ml_artifacts_data`, `trading_artifacts_data` e `trading_outputs_data` são estado persistente. Antes de habilitar rotinas que consumam Trading V2 em um host novo, importe neles o backup de estado que contenha os 632 artifacts e 1.844 outputs; não trate volumes vazios como dados atuais.

## 8. Upgrade

1. Criar e verificar backup.
2. Construir novas imagens identificadas pelo novo SHA.
3. Executar `docker compose up -d` para que `migrate` finalize antes da aplicação.
4. Validar `/health`, `/ready`, Worker, Beat e smoke funcional.
5. Manter imagem anterior disponível até o aceite.

## 9. Rollback

Rollback de imagem não implica downgrade automático de schema. Antes do deploy, classifique a migration como backward-compatible ou planeje janela de restore. Nunca rode downgrade destrutivo no banco canônico por tentativa.

Em falha:

1. impedir novas escritas na borda;
2. coletar logs sanitizados e correlation IDs;
3. voltar imagens somente se compatíveis com o schema atual;
4. se incompatível, restaurar backup em banco novo e validar antes de trocar a conexão;
5. preservar o banco/volume original para análise.

## 10. Shutdown e reboot

```bash
docker compose --env-file .env.production -f docker-compose.production.yml stop
```

Não use `down -v`. As políticas de restart devem recuperar o stack após reboot. Após retorno, valide migration, readiness, Worker e Beat.

## Proibições operacionais

- `docker compose down -v`;
- `docker system prune --volumes`;
- restore sobre o banco canônico;
- segredo no Git, linha de comando gravada no shell ou log;
- exposição pública de 5432, 6379 ou 8000;
- mais de uma instância Beat;
- usar `latest` como única identificação de release.


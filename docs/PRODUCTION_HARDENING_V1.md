# Production Hardening V1

## Escopo

Esta fase torna o VinanceOS implantável em um host Linux com Docker, sem mudar as regras financeiras dos Autopilots 1–6. Cloudflare, DNS e domínio permanecem fora deste escopo.

## Arquitetura

```text
browser
  |
  v
frontend (Nginx, único serviço publicado)
  |-- /                 -> SPA React
  `-- /api/             -> backend FastAPI
                              |-- PostgreSQL
                              `-- Redis

celery_worker  -> Redis/PostgreSQL
celery_beat    -> Redis/PostgreSQL (uma única réplica)
migrate        -> Alembic one-shot antes dos processos da aplicação
```

PostgreSQL, Redis e backend não publicam portas no host no Compose de produção. O navegador usa apenas `/api/v1`, no mesmo origin da SPA.

O backend aceita forwarded headers somente dentro dessa fronteira privada. Nginx substitui `Host`, `X-Real-IP`, `X-Forwarded-For` e `X-Forwarded-Proto`; como a porta 8000 não é publicada, headers arbitrários da internet não chegam diretamente ao Uvicorn.

## Build e identificação

- As dependências Python e Node são instaladas durante o build, sem fallback de instalação no startup.
- A imagem recebe `APP_VERSION` e `APP_COMMIT_SHA` como metadados de implantação.
- `/health` expõe somente estado de vida, versão e SHA; não expõe configuração nem segredos.
- O bundle de produção não pode conter `localhost:8000`, `127.0.0.1:8000` ou endereços residenciais.

## Health, readiness e migrations

`GET /health` verifica que o processo HTTP está vivo. Não depende de PostgreSQL, Redis, Worker ou Beat.

`GET /ready` retorna sucesso apenas quando:

1. PostgreSQL responde;
2. Redis responde;
3. a revisão em `alembic_version` coincide com o head empacotado na aplicação.

O serviço `migrate` é o único responsável por executar `alembic upgrade head`. Backend, Worker e Beat aguardam sua conclusão; eles não tentam migrar concorrentemente.

## Processos

- HTTP: Gunicorn com worker Uvicorn e concorrência configurável por `WEB_CONCURRENCY`.
- Worker: concorrência configurável por `CELERY_WORKER_CONCURRENCY`, conservadora por padrão.
- Beat: uma única instância e arquivo de scheduler em volume próprio.
- Todos os serviços persistentes possuem política de restart e rotação de logs Docker.

## Sessões e autenticação

- O access token é curto e permanece apenas em memória no browser.
- O refresh credential é opaco, rotativo, armazenado no browser em cookie `HttpOnly` e no banco somente como hash.
- Access tokens incluem identificador da sessão (`sid`) e identificador único (`jti`).
- Login, registro, refresh e logout validam a origem em produção quando criam ou consomem a credencial em cookie; mudança de senha exige Bearer válido.
- Logout revoga a sessão antes de remover o cookie.
- Mudança de senha exige a senha atual e revoga todas as sessões do usuário.
- Registro público é controlado por `REGISTRATION_ENABLED`.
- Em produção, cookies usam `Secure`, `HttpOnly`, `SameSite` e path limitado à API.
- Operações baseadas no cookie validam `Origin`/`Referer`; as APIs normais continuam usando Bearer em memória.

Não há recuperação self-service por e-mail nesta V1. O procedimento administrativo está no `SECURITY_RUNBOOK.md`.

## Rate limiting

Login, registro, refresh, troca de senha e outras operações sensíveis usam limites direcionados. Login possui buckets independentes por IP e por identificador normalizado; os demais gates usam a menor chave necessária ao contexto. Redis fornece coordenação entre processos, sem registrar senha, token ou payload financeiro e sem depender da memória isolada de um worker web.

## Nginx e cache

- `index.html`: `Cache-Control: no-cache`.
- `/assets/` com hash: cache longo e `immutable`.
- APIs autenticadas: `Cache-Control: private, no-store`.
- SPA fallback somente no frontend; `/api/` nunca cai em `index.html`.
- `/docs`, `/redoc` e `/openapi.json` não caem no SPA e ficam fechados no edge de produção.
- CSP de produção usa `connect-src 'self'` e não possui exceções de LAN.
- HSTS não é ativado antes da validação do HTTPS real na Fase F.

## Configuração segura

Produção falha rapidamente quando encontra:

- segredo JWT ausente, curto ou placeholder;
- senha/URL padrão de PostgreSQL ou Redis;
- CORS wildcard, origem não HTTPS ou origem placeholder;
- hosts confiáveis vazios;
- debug ou demo habilitados.

`.env.production.example` contém somente nomes e placeholders, nunca credenciais reais.

## Backup e restore

O backup usa `pg_dump --format=custom`, valida arquivo não vazio, gera SHA-256 e cifra com AES-256-CBC/PBKDF2 usando segredo fora do Git. A retenção mantém até 7 diários, 4 semanais e 3 mensais.

Uma cópia no mesmo host é apenas staging local. Para produção real, o artefato cifrado deve ser enviado para armazenamento externo na Fase F.

Restore aceita somente um banco-alvo explicitamente informado por ambiente e vazio. Nunca aponta implicitamente para o banco canônico. O drill obrigatório restaura em PostgreSQL isolado e verifica checksum, revisão Alembic, constraints e contagens essenciais; o smoke da aplicação restaurada é executado separadamente pelo runbook.

## Estado persistente

Obrigatório preservar:

- volume PostgreSQL;
- scheduler do Celery Beat, quando aplicável;
- backups cifrados até envio off-host;
- artifacts e outputs do Trading V2, quando residirem fora do PostgreSQL.

Modelos da aplicação e artifacts/outputs de Trading possuem volumes nomeados compartilhados entre backend e Worker. Em um host novo, os artifacts existentes devem ser importados a partir do backup de estado antes de qualquer rotina que os consuma; volumes vazios nunca são tratados como os 632 artifacts e 1.844 outputs atuais.

Redis, caches de build e dados reconstruíveis não substituem backup.

## Limites explícitos

- Sem Cloudflare Tunnel, DNS, HSTS definitivo ou certificado nesta fase.
- Sem e-mail externo para recuperação de senha.
- Sem execução de investimentos ou integração com corretora.
- Trading V2 permanece `PAPER_ONLY`, isolado do Autopilot.
- Crypto Investment e Trading Console continuam fora da V1 funcional.

# VinanceOS — Production Readiness

Data da auditoria: 27/08/2026  
Fase: 38 — Hardening, QA Final, Auditoria Técnica e Production Readiness  
Classificação: **CONDITIONALLY_READY**

## 1. Conclusão executiva

O runtime ativo do VinanceOS está funcional, reconstruível e consistente para homologação controlada. Backend, frontend, PostgreSQL, Redis, Celery worker e Celery Beat sobem via Docker; o backend, o banco, o Redis, o worker e o Beat terminam saudáveis; `/login` e `/investir` respondem; as APIs autenticadas recusam acesso anônimo; as migrations 0015–0017 foram validadas em banco isolado; e as regressões canônicas passaram sem falhas.

A classificação não é `PRODUCTION_READY` porque a evidência disponível ainda não fecha requisitos operacionais de produção:

1. não existem decisões, avaliações, subscriptions ou alertas reais para validar comportamento longitudinal;
2. o metadata principal do Alembic não declara tabelas ML/trading existentes no banco;
3. há um advisory transitivo sem versão corrigida para `ecdsa 0.19.2`;
4. o frontend mantém o bearer token em `localStorage`;
5. não há rate limiting distribuído ou no reverse proxy;
6. a avaliação histórica da Fase 36 possui um N+1 potencial antes de volume representativo;
7. a suíte histórica em `tests/` ainda contém contratos arquivados fora da suíte canônica;
8. não foi realizado exercício real de restore, carga autenticada representativa ou deploy em infraestrutura de produção.

Nenhuma regra financeira, score, guardrail, modelo de ML ou decisão histórica foi alterada para obter resultados verdes.

## 2. Escopo e preservação

- Branch/HEAD observado no início: `feature/trading-feature-store-v2`, `a4fce6f`.
- O worktree já estava extensamente modificado antes da Fase 38.
- Nenhuma mudança preexistente foi resetada ou descartada.
- Nenhum usuário, decisão, avaliação, subscription ou alerta foi fabricado no banco real.
- Fixtures e overrides foram usados apenas em testes isolados.
- Não houve commit, push ou merge.
- Atribuição exata de todos os arquivos do worktree a uma fase não é possível sem um baseline limpo anterior; este relatório separa as mudanças diretamente auditadas na Fase 38 das mudanças encontradas no snapshot.

## 3. Arquitetura atual

| Serviço | Responsabilidade | Persistência/dependência | Estado final |
|---|---|---|---|
| Frontend React/Vite/Nginx | Login, `/investir`, histórico, performance e alertas | API HTTP | HTTP 200 |
| FastAPI backend | Auth, Recommendation Engine, auditoria, performance e alertas | PostgreSQL e Redis | healthy |
| PostgreSQL 16 | Dados transacionais, snapshots e histórico | volume `postgres_data` | healthy |
| Redis 7 | Broker/result backend Celery | volume `redis_data` | healthy |
| Celery worker | Tarefas de mercado, performance e alertas | Redis/PostgreSQL | healthy, não-root |
| Celery Beat | Schedules existentes | Redis/worker | healthy, não-root |

PostgreSQL e Redis ficaram acessíveis somente pela rede interna do Compose. O frontend continua publicado em `3000` e o backend em `8000` para o ambiente local.

## 4. Fluxos auditados

### 4.1 Decisão

`/investir` → sessão autenticada → `GET /api/intelligence/budget-advisor?explain=true` → normalização frontend → Recommendation Engine oficial → snapshot/auditoria Fase 35 → `decision_id`/`correlation_id` → componentes de decisão.

O hardening não alterou os cálculos do Recommendation Engine. Entradas não finitas, orçamento não positivo, preço/score inválido e ativos duplicados passaram a ser tratados na fronteira sem fabricar recomendação.

### 4.2 Auditoria

Requisição autenticada → IDs preservados/gerados → captura dos inputs, scores, guardrails, explicação e versões → `investment_decision_audits` → histórico/detalhe com filtro obrigatório de `user_id`.

### 4.3 Performance

Decisão auditada → maturação 1d/7d/30d → coleta de preço de referência/avaliação → classificação observacional → `investment_decision_performance` → resumo e detalhe.

### 4.4 Alertas

Subscription → tarefa periódica → nova decisão auditada → comparação com estado anterior → thresholds → cooldown/deduplicação → alerta `IN_APP` → leitura pelo proprietário.

## 5. APIs recentes validadas

### Decisões

- `GET /api/v1/investments/decisions`
- `GET /api/v1/investments/decisions/metrics`
- `GET /api/v1/investments/decisions/{decision_id}`

### Performance

- `GET /api/v1/investments/performance`
- `GET /api/v1/investments/decisions/{decision_id}/performance`

### Monitoramento e alertas

- `GET /api/v1/investments/alert-subscriptions`
- `POST /api/v1/investments/alert-subscriptions`
- `PATCH /api/v1/investments/alert-subscriptions/{subscription_id}`
- `DELETE /api/v1/investments/alert-subscriptions/{subscription_id}`
- `GET /api/v1/investments/alerts`
- `GET /api/v1/investments/alerts/metrics`
- `GET /api/v1/investments/alerts/{alert_id}`
- `PATCH /api/v1/investments/alerts/{alert_id}/read`

Todas as rotas acima exigem autenticação. Consultas, detalhes, updates, deletes e marcação de leitura combinam identificador e `user_id`, evitando IDOR e não revelando ownership alheio.

## 6. Migrations e banco

Head observado e aplicado: `0017_investment_alerts`.

| Migration | Estrutura principal | Resultado isolado |
|---|---|---|
| 0015 | `investment_decision_audits` | upgrade, unique `decision_id`, FKs e índices validados |
| 0016 | `investment_decision_performance` | upgrade, FK e unique `(decision_id, horizon)` validados |
| 0017 | subscriptions, estados e alertas | upgrade, checks, FKs, uniques e índices validados |

Em PostgreSQL efêmero e isolado:

- upgrade base → 0017: aprovado;
- downgrade 0017 → 0014: removeu somente as cinco tabelas das Fases 35–37;
- re-upgrade até 0017: aprovado;
- nenhum dado real foi tocado.

Integridade observada nas tabelas recentes:

- orphan rows: 0;
- duplicações em chaves naturais/únicas: 0;
- constraints não validadas: 0;
- índices esperados para histórico, ownership, inbox e deduplicação: presentes.

### Drift conhecido

`alembic check` ainda acusa:

- tabelas e índices ML/trading existentes no banco, mas ausentes do metadata carregado pelo Alembic principal;
- seis índices redundantes de `id` declarados pelos models e ausentes no banco.

O drift é preexistente e não afeta o head 0017, mas impede declarar o schema global totalmente convergente. Não foi usado `autogenerate` e nenhuma tabela foi apagada. Antes de produção, é necessário definir ownership explícito: incorporar os metadatas ML/trading ao Alembic ou excluí-los formalmente da comparação.

## 7. Estado real dos dados

Após rebuild, restart e execução real das tarefas periódicas:

| Recurso | Quantidade real |
|---|---:|
| Usuários existentes | 1 |
| Decisões Fase 35 | 0 |
| Avaliações Fase 36 | 0 |
| Subscriptions Fase 37 | 0 |
| Estados monitorados | 0 |
| Alertas Fase 37 | 0 |

As tarefas executaram com sucesso sobre esse estado:

- performance: 0 decisões varridas, 0 avaliações criadas;
- alertas: 0 subscriptions varridas, 0 alertas, 0 erros.

Não havia dados reais suficientes para observar mudança de recomendação, performance histórica ou alerta. A cobertura desses fluxos veio de fixtures isoladas e não deve ser confundida com atividade real.

## 8. Schedules finais

Timezone dos serviços: `America/Sao_Paulo`.

- avaliação de performance: diariamente às 05:30;
- avaliação de alertas: diariamente às 22:10, depois de scores (21:35), guardrails (21:45) e trends (21:55);
- ambas usam a fila `intelligence`.

A ordem evita avaliar alertas antes da atualização das fontes financeiras. Não foi criado scheduler paralelo.

## 9. Segurança

### Autenticação e autorização

- ausência, expiração ou invalidade do bearer token: 401;
- usuário inativo/removido: token rejeitado;
- reload autenticado e logout: cobertos;
- ownership A/B de decisões, performance, subscriptions e alertas: coberto por testes;
- IDs inválidos e filtros inválidos: 4xx, sem 500 comum;
- schemas de login/registro rejeitam campos desconhecidos e limitam tamanho da senha.

### Configuração

Em ambiente de produção, a aplicação rejeita:

- segredo JWT fraco/default;
- senha/default de banco;
- Redis/default inseguro;
- CORS wildcard ou origens locais.

O `.env` real não foi alterado. Templates devem ser preenchidos pelo mecanismo de secrets do deploy.

### Logs

- redação para Bearer, authorization, password, token, cookie, API key e secret;
- nenhuma linha correspondente encontrada nos logs finais;
- nenhum traceback ou warning de execução como root encontrado;
- payloads financeiros/sensíveis completos não são despejados.

### Headers

Backend e Nginx entregam `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e `Permissions-Policy`. O Nginx também entrega CSP com `default-src 'self'`, bloqueio de objetos e `frame-ancestors 'none'`.

CORS usa allowlist configurável e credenciais; wildcard é rejeitado em produção.

### Frontend

- React continua fazendo escaping padrão;
- nenhum `dangerouslySetInnerHTML` foi encontrado;
- parâmetros e conteúdo da API não são transformados em HTML bruto;
- modal recebeu `role=dialog`, `aria-modal`, foco inicial, trap de foco, Escape e restauração de foco;
- risco residual: token em `localStorage`, vulnerável a exfiltração caso um XSS futuro seja introduzido.

### Rate limiting

Existe um helper legado em memória, mas ele não está ligado ao app ativo e não é seguro para múltiplos workers/instâncias. Não foi ativado para produzir falsa sensação de proteção. Login, recommendation e subscriptions devem receber rate limiting no API gateway/reverse proxy ou em mecanismo distribuído antes da exposição pública.

## 10. Dependências

### Frontend

- situação inicial: 16 vulnerabilidades (`1 critical`, `9 high`, `6 moderate`);
- situação final: `npm audit` e `npm audit --omit=dev` com 0 vulnerabilidades;
- lint, typecheck e build aprovados;
- atualizações incompatíveis não foram forçadas com `npm audit fix --force`.

### Backend

- `pip check`: sem dependências quebradas;
- rebuild instala integralmente o `requirements.txt`, sem instalação manual posterior;
- `pip-audit`: somente `ecdsa 0.19.2 / PYSEC-2026-1325`, sem fix version publicada;
- o JWT ativo usa `HS256`; o pacote vulnerável chega transitivamente por `python-jose[cryptography]` e não é chamado pelo algoritmo configurado, mas permanece no ambiente e deve ser removido por migração planejada da biblioteca JWT.

Warnings de evolução:

- `passlib` usa `crypt`, removido no Python 3.13;
- `Starlette TestClient` sinaliza migração futura para `httpx2`;
- scikit-learn/SciPy emitiram 21 warnings sobre opções L-BFGS-B futuras;
- Recharts 2 está em linha antiga, embora sem advisory npm atual; migração para v3 exige projeto separado.

## 11. Docker

Hardening aplicado:

- backend, worker e Beat rodam como `vinance`, UID/GID 10001;
- `COPY --chown` e diretórios de runtime com ownership correto;
- healthchecks reais para backend, PostgreSQL, Redis, worker e Beat;
- PostgreSQL e Redis sem portas publicadas no host;
- `.dockerignore` raiz exclui Git, caches, frontend, trading, archives, logs e artefatos não usados pelo backend ativo;
- `.dockerignore` frontend preserva somente os arquivos necessários ao build;
- dependência Linux usa `xgboost-cpu`, eliminando layers CUDA/NCCL sem uso.

| Imagem | Antes | Depois | Variação aproximada |
|---|---:|---:|---:|
| backend | 2,47 GB | 1,02 GB | -59% |
| celery worker | 2,47 GB | 1,02 GB | -59% |
| celery beat | 2,47 GB | 1,02 GB | -59% |
| frontend | 74,3 MB | 74,3 MB | estável |

Contexto observado no rebuild final: aproximadamente 71 kB para o backend e 13–18 kB para o frontend. O rebuild final usou somente Dockerfiles e lockfiles; nenhuma instalação manual foi necessária.

Cold start local observado:

- Compose recriou app/worker/beat e iniciou o frontend em aproximadamente 20 segundos;
- todos os healthchecks, inclusive worker e Beat, apareceram verdes em aproximadamente 45 segundos, condicionado ao intervalo do healthcheck.

Restart individual de backend, frontend, worker, Beat e Redis foi validado. Ao reiniciar Redis, o worker registrou falha de conexão transitória e reconectou em cerca de dois segundos; o backend voltou a `healthy`.

## 12. Performance observada

Amostra local de 30 chamadas por endpoint. Somente `/health` foi happy path; as APIs protegidas foram medidas sem credenciais, portanto os números refletem principalmente o caminho 401 e não carga autenticada de produção.

| Endpoint | Resultado | Média | P95 | Máximo |
|---|---|---:|---:|---:|
| `/health` | 200 | 16,34 ms | 26,26 ms | 175,71 ms |
| `/api/v1/me` | 401 | 13,23 ms | 41,01 ms | 150,79 ms |
| budget-advisor | 401 | 17,18 ms | 11,34 ms | 320,03 ms |
| decisions | 401 | 42,74 ms | 23,95 ms | 988,44 ms |
| decision metrics | 401 | 8,16 ms | 11,06 ms | 15,19 ms |
| performance | 401 | 8,61 ms | 12,46 ms | 20,35 ms |
| alerts | 401 | 9,62 ms | 26,33 ms | 29,06 ms |
| subscriptions | 401 | 7,11 ms | 13,30 ms | 18,39 ms |

Os outliers são de uma máquina local e não equivalem a SLA. É obrigatório repetir com usuário autenticado, dataset representativo, warm/cold cache e concorrência real antes de definir SLO.

### Queries

`EXPLAIN` confirmou uso de índices para histórico de decisões, inbox de alertas e performance por `(decision_id, horizon)`. O planner escolheu scan sequencial para subscriptions em tabela vazia/pequena, comportamento esperado.

Risco residual: a tarefa diária da Fase 36 consulta preços de referência, avaliação e excursão por decisão/horizonte. Com volume alto isso forma N+1; não foi refatorado sem dataset e benchmark representativos porque toca um fluxo financeiro sensível.

## 13. Testes finais

### Suítes canônicas

| Suíte | Resultado | Falhas | Skips | Collection errors |
|---|---:|---:|---:|---:|
| `backend/tests` | 420/420 | 0 | 0 | 0 |
| `backend/app/tests` | 3/3 | 0 | 0 | 0 |
| `backend/trading` | 127/127 | 0 | 0 | 0 |
| frontend Node + Vitest | 68/68 | 0 | 0 | 0 |
| E2E Chromium | 11/11 | 0 | 0 | 0 |

Total canônico sem contar matrizes sobrepostas: **629/629**.

Matrizes financeiras:

- Fases 22–31: 48/48;
- Intelligence Base / `emergency_reserve_priority`: 12/12;
- Recommendation Engine ampliado: referência Fase 37 em 106/106;
- superconjunto reexecutado na Fase 38: 108/108.

Frontend:

- lint: aprovado;
- typecheck app + testes: aprovado;
- Vite 8.2.2: aprovado, 1.676 módulos;
- bundle principal: 402,23 kB, gzip 123,63 kB;
- console inesperado/unhandled rejection na jornada E2E: 0;
- overflow horizontal em desktop, tablet, 390 px e 320 px: 0 nos cenários E2E.

### Suíte histórica fora do `pytest.ini`

O `pytest.ini` canônico limita a coleta a `backend/tests`. A pasta raiz `tests/` contém artefatos do backend empresarial anterior:

- `test_intelligent_investing.py` e `test_quant_intelligence.py` são byte a byte idênticos às cópias em `_archived/phase1_core_backend/root_tests_legacy` e importam schemas removidos; a coleta integral da pasta raiz produz dois collection errors;
- excluindo somente essas duas duplicatas, 108/110 passam;
- os dois contratos restantes inspecionam strings de uma autenticação enterprise não montada e exigem quatro endpoints operacionais legados (`/health`, `/ready`, `/live`, `/metrics`) enquanto o runtime atual mantém apenas `/health` composto.

Esses testes não foram apagados, ignorados no `pytest.ini` ou enfraquecidos. É necessária decisão explícita de canonização: remover as duplicatas já arquivadas e migrar os dois contratos de fonte para testes funcionais do app atual, ou reativar formalmente a aplicação enterprise. Recriar classes antigas apenas para mascarar a coleta seria incorreto.

## 14. Bugs encontrados e severidade

| Severidade | Encontrados | Corrigidos | Restantes |
|---|---:|---:|---:|
| BLOCKER | 2 | 2 | 0 |
| HIGH | 6 | 6 | 0 |
| MEDIUM | 11 | 5 | 6 |
| LOW | 4 | 1 | 3 |
| INFORMATIONAL | 5 | 0 | 5 |

BLOCKER corrigidos:

1. import removido `SessionLocal` quebrava coleta;
2. import removido `FinancialDecisionHistory` quebrava coleta.

HIGH corrigidos:

1. cadeia npm com vulnerabilidades critical/high;
2. worker/Beat/backend executando como root;
3. defaults fracos permitidos em produção;
4. PostgreSQL/Redis publicados no host;
5. validação 422 convertida indevidamente em 500;
6. redação insuficiente de segredos em logs.

MEDIUM corrigidos:

1. headers de segurança ausentes;
2. modal sem foco/teclado/ARIA completos;
3. orçamento, score e preço não finitos/duplicados;
4. imagens e contexto Docker excessivos;
5. fixtures de sincronização incompatíveis com persistência append-only/upsert atual.

MEDIUM restantes:

1. advisory transitivo `ecdsa`;
2. token em `localStorage`;
3. ausência de rate limiting distribuído;
4. drift global de metadata/Alembic;
5. N+1 potencial da Fase 36;
6. suíte histórica raiz não canonizada.

LOW/INFORMATIONAL restantes incluem warnings de futuras versões, ausência de healthcheck Nginx dedicado, ausência de endpoints distintos de liveness/readiness, falta de histórico real e falta de testes de carga/restore em infraestrutura externa.

## 15. Matriz final de QA

| Área | Status | Evidência | Risco restante |
|---|---|---|---|
| Authentication | Aprovada com ressalva | 401, expiração, reload, logout, E2E | token em `localStorage` |
| Authorization | Aprovada | ownership A/B e 404 indistinguível | repetir em staging multiusuário |
| Recommendation | Aprovada | matrizes 48/48, 12/12, superconjunto 108/108 | sem carga real extrema |
| Investir UI | Aprovada | unit/integration/E2E | browser manual indisponível |
| Audit | Aprovada com ressalva | testes F35 e migration 0015 | zero decisões reais |
| Performance histórica | Aprovada com ressalva | testes F36 e migration 0016 | N+1 e zero amostras reais |
| Alerts | Aprovada com ressalva | testes F37, Celery real vazio | zero alertas reais |
| Celery | Aprovada | worker/Beat healthy, tarefas SUCCESS | monitorar backlog em staging |
| Database | Aprovada com ressalva | integridade e EXPLAIN | drift ML/trading |
| Migrations | Aprovada com ressalva | upgrade/downgrade/re-upgrade isolado | metadata global não converge |
| Docker | Aprovada | build, non-root, restart, health | Nginx sem healthcheck dedicado |
| Security | Condicional | headers, CORS, logs, deps | rate limit, localStorage, ecdsa |
| Frontend | Aprovada | 68/68, build/typecheck/lint | debt Recharts v2 |
| E2E | Aprovada | 11/11 | fixtures, não dados reais |
| Observability | Aprovada com ressalva | JSON logs e métricas F35–37 | sem stack central externa |
| Performance/Latency | Condicional | amostra local e EXPLAIN | sem carga autenticada representativa |

## 16. Observabilidade e recovery

Logs estruturados carregam, quando aplicável, `decision_id`, `correlation_id`, `user_id`, asset, subscription, alerta, tipo, severidade, status e latência. As tarefas expõem contadores de decisões avaliadas, alertas gerados, cooldown, duplicados e erros.

`/health` retorna estado separado de API, banco e Redis e responde 503 quando uma dependência falha. O endpoint não expõe DSN, host, versão de banco ou segredo. Para Kubernetes/orquestrador equivalente, recomenda-se separar futuramente liveness de readiness, mantendo `/health` para compatibilidade.

## 17. Backup e restore recomendados

Antes de qualquer deploy:

1. executar `pg_dump` consistente do banco completo;
2. registrar a revisão Alembic e checksums das imagens;
3. preservar volumes PostgreSQL e Redis conforme RPO/RTO definido;
4. criptografar backups e limitar acesso por função;
5. testar restore em banco isolado, aplicar `alembic upgrade head` e executar smoke tests;
6. validar especificamente snapshots 0015, avaliações 0016 e alertas 0017 após restore;
7. documentar retenção, rotação e recuperação pontual do PostgreSQL.

Nenhum exercício de restore real foi executado nesta fase; isso é gate de produção.

## 18. Deploy e rollback

Deploy recomendado:

1. congelar imagem e lockfiles validados;
2. obter backup e confirmar restore testado;
3. aplicar migrations em job único antes de escalar workers;
4. subir backend e validar `/health`;
5. subir worker e Beat, garantindo somente um Beat ativo;
6. subir frontend e executar smoke `/login` → `/investir`;
7. habilitar tráfego gradualmente e observar 401/4xx/5xx, latência, queue depth e erros de auditoria.

Rollback recomendado:

- rollback de aplicação: voltar às imagens anteriores compatíveis, sem downgrade automático do banco;
- rollback de schema: somente com backup validado e procedimento específico; migrations 0015–0017 preservam histórico por FKs/constraints e downgrade pode remover tabelas;
- nunca usar autogenerate destrutivo para corrigir o drift ML/trading;
- pausar Beat antes de qualquer intervenção que possa duplicar schedules.

## 19. Gates para `PRODUCTION_READY`

1. Canonizar/remover com aprovação os testes históricos duplicados e obter coleta global inequívoca.
2. Resolver o advisory `ecdsa` por migração segura da biblioteca JWT ou isolamento comprovado.
3. Implementar rate limiting distribuído no gateway para login, recommendation e subscriptions.
4. Migrar autenticação web para cookie `HttpOnly`, `Secure`, `SameSite` ou registrar aceitação formal do risco.
5. Resolver ownership do schema ML/trading no Alembic.
6. Executar carga autenticada com volume representativo e tratar o N+1 da Fase 36 se confirmado.
7. Executar backup/restore drill e validar RPO/RTO.
8. Validar o ciclo completo com decisões, performance, subscriptions e alertas reais em staging, sem fabricar dados de produção.
9. Centralizar logs/métricas e configurar alertas operacionais de fila, erro, latência e falha de auditoria.

## 20. Resposta final de readiness

O VinanceOS está tecnicamente pronto para **homologação controlada e piloto interno**, com o runtime ativo verde e reproduzível.

O VinanceOS **ainda não possui evidência suficiente para exposição pública irrestrita em produção**. A classificação final desta Fase 38 é `CONDITIONALLY_READY` até que os gates da seção 19 sejam fechados.

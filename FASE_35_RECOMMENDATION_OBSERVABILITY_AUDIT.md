# Fase 35 — Observabilidade, Auditoria e Rastreabilidade das Recomendações

## Status

A trilha auditável do `budget-advisor` foi implementada de ponta a ponta sem alterar fórmulas, pesos, guardrails, classificação financeira, ML ou trading.

O fluxo validado é:

```text
/investir
  -> sessão autenticada
  -> X-Decision-ID + X-Correlation-ID
  -> GET /api/intelligence/budget-advisor?explain=true
  -> contexto estruturado de rastreabilidade
  -> Recommendation Engine existente
  -> snapshot sanitizado e imutável da resposta
  -> investment_decision_audits
  -> resposta com decision_id/correlation_id
  -> histórico e detalhe exclusivos do usuário
```

## Arquitetura

### Identificadores

- O frontend cria UUIDs independentes para `decision_id` e `correlation_id` em cada consulta.
- O backend preserva UUIDs válidos enviados nos headers `X-Decision-ID` e `X-Correlation-ID`.
- IDs ausentes ou inválidos são substituídos no backend por UUIDs seguros.
- O mesmo par acompanha o contexto da execução, resposta, headers, logs e registro persistido.
- Cada nova reconsulta cria um novo par de IDs.
- `decision_id` possui constraint única no banco; repetir a mesma decisão na mesma execução não duplica o registro.

Exemplo isolado, sem dados pessoais:

```json
{
  "decision_id": "526a0cc0-c068-4d35-9962-9e191d22d876",
  "correlation_id": "a9dcc0dc-0a84-4d79-8158-006a5ca5acae"
}
```

### Persistência aditiva

A migration `0015_decision_audits`, sucessora de `0014_asset_trend_signals`, cria `investment_decision_audits` sem remover ou modificar tabelas existentes.

O registro contém:

- identidade: `decision_id`, `correlation_id`, `user_id`, `created_at`;
- contexto: ativo, mercado, orçamento e perfil;
- decisão: ação apresentada, quantidade, preço, valor investido e saldo;
- leitura: risco, confiança, tendência, ranking e recommendation score;
- guardrails: status e motivos;
- snapshots JSON: parâmetros, inputs, scores, explicação e resposta;
- versões: schema, regras, engine, scores, guardrails e tendência;
- operação: latência, fallback, código de erro e status.

Índices compostos por usuário atendem ordenação e filtros de data, ação, risco e ativo. `decision_id` é único e `user_id` referencia `users.id` com `RESTRICT`.

### Snapshots

Cada resposta é convertida para uma estrutura JSON independente antes da persistência. `Decimal`, datas, UUIDs, dataclasses e objetos de domínio são serializados sem manter referência mutável aos dados correntes.

Alterações futuras em preço, perfil, score, tendência, guardrail ou engine não reescrevem os snapshots anteriores. Não foram criados endpoints de update ou delete para decisões.

A sanitização é recursiva e remove chaves relacionadas a:

- senha;
- authorization/bearer;
- access/refresh token;
- cookie;
- secret;
- API key.

Valores textuais iniciados por `Bearer` também são redigidos.

### Versionamento

O versionamento simples e central está em `backend/app/investment_decisions/versions.py`:

- snapshot: `investment-decision-audit-v1`;
- engine: `budget-advisor-v1`;
- regras de apresentação: `investment-decision-presentation-v1`;
- score, guardrail e tendência: versões/fontes já declaradas pelos serviços atuais.

Esse versionamento identifica a regra vigente sem introduzir uma infraestrutura paralela de releases.

## Integração com o Budget Advisor

O endpoint mantém o payload financeiro existente e acrescenta, apenas nas respostas estruturadas:

- `decision_id`;
- `correlation_id`;
- `generated_at`;
- `decision_action`;
- `audit_status`.

Os IDs também são devolvidos em `X-Decision-ID` e `X-Correlation-ID`. As respostas usam `Cache-Control: private, no-store`, e os headers são expostos pelo CORS.

A ação auditada espelha a tradução visual já existente no frontend. Nenhuma classificação é enviada de volta ao Recommendation Engine nem participa dos cálculos.

### Política de falha

A auditoria é `fail-open` para o resultado financeiro:

1. o Recommendation Engine calcula a resposta normalmente;
2. a auditoria tenta persistir exatamente esse resultado;
3. se o insert falhar, a transação é revertida e o erro operacional é registrado;
4. a recomendação original continua sendo devolvida com `audit_status: FAILED`.

Assim, uma falha de observabilidade não produz outra recomendação. Erros do próprio engine são registrados, quando o banco está disponível, com status `ERROR` e código seguro.

## Observabilidade e métricas

Os eventos estruturados são:

- `investment_decision.started`;
- `investment_decision.completed`;
- `investment_decision.failed`;
- `investment_decision.fallback`;
- `investment_decision.audit_persistence_failed`.

Todos os eventos do fluxo carregam `decision_id`, `correlation_id` e `user_id` pelo contexto da requisição. Ativo, status, latência, fallback e código de erro são incluídos quando aplicáveis.

O formatter JSON usa uma lista explícita de campos e redige Bearer tokens. A validação dos logs reais do container encontrou zero ocorrências de `Bearer`, `Authorization`, refresh token e do token inválido usado no teste.

O endpoint de métricas calcula, por usuário autenticado:

- total de decisões;
- Comprar, Aguardar e Evitar;
- erros e fallbacks;
- latência média e P95;
- distribuição por perfil e risco;
- dez ativos mais consultados.

Não foi adicionada stack externa de observabilidade.

## Endpoints

### `GET /api/v1/investments/decisions`

Histórico somente de leitura do usuário atual, mais recente primeiro. Suporta:

- `page` e `page_size`;
- `asset`;
- `action`;
- `date_from` e `date_to`, com timezone;
- `risk_level`.

Ativos aceitam somente caracteres de ticker. Ação e risco usam enums fechados e todos os filtros são construídos pelo SQLAlchemy com parâmetros.

### `GET /api/v1/investments/decisions/{decision_id}`

Retorna o snapshot auditável completo quando o ID pertence ao usuário atual. UUID inválido, inexistente ou pertencente a outra conta recebe a mesma resposta 404, sem revelar ownership.

### `GET /api/v1/investments/decisions/metrics`

Retorna as agregações operacionais somente para decisões do usuário autenticado.

Todos os endpoints exigem autenticação e usam `private, no-store`.

## Frontend

`/investir` mantém a experiência decisória principal e acrescenta:

- identificação discreta e recolhida da decisão atual;
- indicação visual caso a auditoria não tenha sido confirmada;
- histórico recente em seção expansível;
- paginação sem recarregar a recomendação atual;
- estados independentes de loading, vazio e erro;
- painel de detalhe com ação, risco, valor, score, confiança, latência e versões;
- IDs completos apenas dentro da área de rastreabilidade;
- queries separadas por usuário, impedindo reutilização de cache entre contas;
- novo ID em toda reconsulta, inclusive quando os filtros são repetidos.

O histórico não transforma a central em painel técnico e não bloqueia a recomendação quando sua própria consulta falha.

## Segurança

Foram validados:

- 401 para usuário anônimo;
- 401 para token inválido;
- owner aplicado em histórico, detalhe e métricas;
- decisão de outro usuário indistinguível de uma decisão inexistente;
- UUID inválido tratado como 404;
- filtro de ativo rejeita payloads de injection;
- ações e riscos usam valores fechados;
- snapshots removem segredos recursivamente;
- logs não contêm tokens;
- caches HTTP e de frontend são isolados por usuário;
- não foi criado usuário real nem alterado dado pessoal para testes.

## Arquivos criados

- `.dockerignore`;
- `backend/alembic/versions/0015_create_investment_decision_audits.py`;
- `backend/app/core/trace.py`;
- `backend/app/investment_decisions/__init__.py`;
- `backend/app/investment_decisions/models.py`;
- `backend/app/investment_decisions/router.py`;
- `backend/app/investment_decisions/schemas.py`;
- `backend/app/investment_decisions/service.py`;
- `backend/app/investment_decisions/versions.py`;
- `backend/tests/test_fase35_investment_decision_audit.py`;
- `frontend/src/features/investment-workspace/components/DecisionHistoryPanel.tsx`;
- `frontend/src/features/investment-workspace/components/DecisionTraceMeta.tsx`;
- `frontend/src/features/investment-workspace/services/investmentDecisionHistory.service.ts`;
- `frontend/tests/unit/investmentDecisionHistory.test.tsx`;
- `frontend/tests/unit/investmentWorkspaceTrace.service.test.ts`;
- `FASE_35_RECOMMENDATION_OBSERVABILITY_AUDIT.md`.

## Arquivos alterados

- `backend/alembic/env.py`;
- `backend/app/api/v1/router.py`;
- `backend/app/core/errors.py`;
- `backend/app/core/logging.py`;
- `backend/app/intelligence/router.py`;
- `backend/app/main.py`;
- `frontend/src/features/investment-workspace/components/index.ts`;
- `frontend/src/features/investment-workspace/services/investmentWorkspace.service.ts`;
- `frontend/src/features/investment-workspace/types/investmentWorkspace.types.ts`;
- `frontend/src/pages/InvestmentWorkspacePage.tsx`;
- `frontend/src/services/api.ts`;
- `frontend/src/styles/global.css`;
- `frontend/tests/e2e/investment-auth.spec.ts`;
- `frontend/tests/fixtures/investmentFixtures.ts`.

Nenhum arquivo de Recommendation Engine, pesos, fórmulas, guardrails, ML ou trading foi alterado nesta fase.

## Validações executadas

### Fase 35 e autenticação

- Backend Fase 35: 23/23 aprovados.
- Backend Fase 34: 3/3 aprovados.
- Frontend Node/Vitest: 40/40 aprovados.
- E2E Chromium: 7/7 aprovados.
- Total específico Fase 34/35: 73/73 aprovados.

O E2E cobre autenticação, `/investir`, geração da recomendação, captura do `decision_id`, histórico, localização da decisão, detalhe, ação/ativo/valor, logout e novo bloqueio autenticado. Usa fixtures isoladas e não cria usuário no banco.

### Qualidade e build

- `npm run typecheck`: aprovado;
- `npm run lint`: aprovado;
- `npm run build`: aprovado;
- Vite: 1.678 módulos transformados;
- bundle principal: 357,25 kB, 110,67 kB gzip;
- CSS: 51,46 kB, 9,06 kB gzip;
- `git diff --check`: sem erro de whitespace; somente avisos de conversão LF/CRLF do worktree existente.

### Regressão financeira

Foram executados 60 testes relevantes adicionais:

- fases 22, 23, 24, 25, 26, 30 e 31: 47/48 aprovados;
- inteligência base: 11/12 aprovados.

Falhas preservadas e fora do escopo:

1. `test_include_warnings_true_returns_approved_and_warning`: a implementação atual ordena o ativo `APPROVED` antes do ativo `WARNING`, enquanto o teste espera a ordem original por score;
2. `test_emergency_reserve_priority_aumenta_renda_fixa`: falha histórica já conhecida; ambos os cenários retornam 43% de renda fixa.

Essas regras não foram corrigidas porque a Fase 35 proíbe alterações na lógica do Recommendation Engine.

No total, 133 testes foram executados: 131 aprovados e 2 falhas externas conhecidas. Todos os 73 testes específicos da integração autenticada e auditável passaram.

## Docker

- Migration aplicada: `0015_decision_audits (head)`.
- Backend: saudável em `:8000`.
- Frontend: resposta HTTP 200 para `/login` e `/investir` em `:3000`.
- PostgreSQL: saudável.
- Redis: saudável.
- Celery worker e beat: ativos, sem rebuild desnecessário.
- `/health`: HTTP 200 com API, database e Redis em `ok`.
- Histórico anônimo: 401.
- Histórico com token inválido: 401.
- As três novas rotas constam no OpenAPI.

Somente backend e frontend foram recriados. A migration foi aditiva e nenhum dado foi apagado.

## Impacto de performance

O caminho de escrita adiciona um `INSERT` indexado e um `COMMIT` por decisão. A latência registrada representa o tempo do Recommendation Engine antes da persistência, evitando misturar cálculo financeiro com overhead de auditoria.

Histórico e métricas são consultas sob demanda. Índices por usuário reduzem o custo dos filtros principais. Não foi executado benchmark com credencial real, pois não havia credencial de teste disponível e a fase proíbe criar usuário automaticamente.

## Limitações

- Não há painel administrativo global; as métricas expostas são intencionalmente isoladas por usuário.
- Falhas da própria persistência são observáveis em log, mas não podem ser gravadas na mesma tabela indisponível.
- Os snapshots não possuem assinatura criptográfica; a imutabilidade é garantida pelo modelo append-only da API, constraint do ID e cópia JSON histórica.
- Os snapshots duplicam deliberadamente parte dos dados resumidos para preservar o contexto exato. O fluxo atual limita os candidatos, mas retenção e crescimento da tabela devem ser monitorados em produção.
- A checagem adicional pelo navegador integrado não inicializou por falha local do controlador. A mesma jornada visual foi validada com 7 E2E Chromium e HTTP real nos containers.
- As duas falhas de regressão financeira descritas acima permanecem sem alteração.

## Readiness

O critério funcional da Fase 35 foi atendido: uma recomendação em `/investir` pode ser rastreada por `decision_id` até usuário, parâmetros, inputs, scores, guardrails, versões, decisão, explicação e histórico, sem alterar o resultado financeiro.

A implementação está pronta para uso da Fase 35. A suíte específica está 73/73 verde; a suíte financeira global permanece com duas falhas externas documentadas que devem ser tratadas em fase própria de Recommendation Engine.

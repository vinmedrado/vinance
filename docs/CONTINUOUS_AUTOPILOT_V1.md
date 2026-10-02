# Continuous Autopilot V1

## Objetivo

`continuous-autopilot-v1` fecha o ciclo do Financial Autopilot. Ele compara a
última cadeia A1–A5 congelada com a realidade observada em um instante
explícito (`as_of`), identifica mudanças estruturadas e decide se existe motivo
para reavaliar, criar um novo Action Plan e avisar o usuário.

Ele não contém um sexto conjunto de regras financeiras. Financial State,
Financial Policy, Capital Allocation, Investment Orchestrator e Action Plan
continuam sendo as autoridades dos seus respectivos domínios.

## Cadeia e fronteiras

```text
Financial State -> Policy -> Allocation -> Orchestration -> Action Plan
       ^                                                        |
       |                                                        v
nova realidade <- Continuous Autopilot <- change/diff/alert decision
```

Entradas históricas são sempre decisões imutáveis. Uma decisão antiga nunca é
recalculada com mercado ou rulesets futuros. O tempo que influencia uma
avaliação é recebido como `as_of`; o engine determinístico não consulta o
relógio do sistema.

O componente não executa investimento, pagamento, transferência ou operação
de Trading. `speculative_capital` permanece zero e `trading_dispatch` permanece
falso.

## Versões

- Engine: `continuous-autopilot-v1`
- Ruleset: `continuous-autopilot-rules-v1`

Mesmos planos congelados, mesmas categorias de mudança, mesmo `as_of` e mesmo
ruleset produzem o mesmo resultado e os mesmos fingerprints.

## Dependency graph e gate de reavaliação

As categorias são normalizadas antes da decisão:

- `FINANCIAL_DATA`, `PROFILE`, `GOALS`, `DEBT`, `ASSETS`, `HOUSEHOLD`,
  `DATA_QUALITY` e `FRESHNESS` invalidam a cadeia financeira completa A1→A5;
- `MARKET_DATA` e `INVESTMENT_OPPORTUNITY` invalidam somente
  Orchestration→Action Plan quando os fingerprints financeiros permanecem
  compatíveis;
- `POLICY` e `ALLOCATION` invalidam a cadeia completa, pois uma reconstrução
  parcial desses níveis não é um contrato exposto pelos engines atuais.

Uma alteração irrelevante pode resultar em `UNCHANGED`, sem novo snapshot A1–A5.
Quando existe mudança material, a nova cadeia é coerente e liga cada decisão ao
mesmo household. Reuso só é permitido quando os inputs relevantes, versões e
fingerprints são idênticos.

## Change detection

Cada mudança é estruturada com categoria, tipo, entidade, valor anterior,
valor atual, delta, severidade, materialidade, razão, fonte, `observed_at`,
`as_of` e fingerprints anterior/atual. Ausência permanece `null`; nunca é
convertida em zero.

Os planos são comparados por campos e IDs estáveis, não por texto renderizado.
O diff contém:

- ações adicionadas, removidas, alteradas e quantidade de inalteradas;
- alterações de tipo, prioridade, ownership, status e valor;
- transições como `BUY -> WAIT`, `BUY -> AVOID` e `WAIT -> BUY`;
- deltas financeiros, de investimento e de caixa preservado;
- alteração do status geral do plano.

## Materialidade

O ruleset centraliza `NONE`, `LOW`, `MEDIUM`, `HIGH` e `CRITICAL`. Transições de
segurança, blockers, downgrade de investment readiness e `BUY -> AVOID` possuem
precedência sobre variações cosméticas. Pequenas mudanças sem efeito no plano
não geram alerta. Os thresholds de change detection pertencem ao ruleset e não
duplicam thresholds dos engines financeiros.

Para valores monetários comparáveis, o ruleset usa o limite absoluto versionado
de `1,00` unidade da moeda canônica (`R$ 1,00` em BRL): variação menor que
`1,00` é `LOW`; variação igual ou maior que `1,00` é `MEDIUM`; e a transição
entre valor ausente e conhecido é `MEDIUM`, inclusive `null -> 0`. Mudanças
`LOW` permanecem auditáveis, mas são suprimidas da inbox. Esse limite classifica
a relevância da mudança; ele não é uma regra financeira ou recomendação de
valor.

## Estados operacionais

O estado mutável, um por household, usa:

- `UP_TO_DATE`
- `REEVALUATION_REQUIRED`
- `EVALUATING`
- `CHANGED`
- `UNCHANGED`
- `BLOCKED`
- `FAILED`

`FAILED` é falha técnica; `UNCHANGED` é um resultado financeiro válido. O
último Action Plan bom permanece disponível em falhas de provedor.

## Alert decision e deduplicação

O resultado de alerta é um de `NO_ALERT`, `INFORMATIONAL`,
`ACTION_RECOMMENDED`, `IMPORTANT` ou `CRITICAL`. A decisão inclui o que mudou,
por que importa, ação recomendada e referências anterior/atual.

A entrega reutiliza a inbox `investment_alerts` em vez de criar uma segunda
caixa de entrada. A extensão diferencia `INVESTMENT` de
`CONTINUOUS_AUTOPILOT`, mantém `read_at`, canal `IN_APP` e deduplicação. Eventos
`PERSONAL` são entregues somente ao owner; eventos `HOUSEHOLD` são entregues a
membros ativos autorizados. A dedupe key inclui decisão e destinatário.

Uma condição idêntica não gera alerta diário. Um novo alerta só aparece quando
o fingerprint, a severidade ou a evidência material muda, ou quando uma
condição resolvida reaparece.

## Persistência e concorrência

`continuous_autopilot_decisions` contém a decisão congelada, planos anterior e
atual, payload estruturado, versões, fingerprints, materialidade, alerta e
timestamps. UPDATE, DELETE e TRUNCATE são rejeitados no PostgreSQL.

`continuous_autopilot_states` contém somente coordenação operacional e
contadores. O payload congelado nunca é alterado para representar esse estado:
a API expõe `operational_status`, categorias pendentes e os timestamps da
última tentativa separadamente do `status` auditável da decisão. Uma avaliação
usa lock por household (`pg_advisory_xact_lock` e row lock), nunca lock global.
Unicidade de fingerprint e dedupe impede decisões e alertas duplicados em
retries ou workers concorrentes.

`continuous_autopilot_requests` é o ledger imutável de idempotência. Sua chave
primária é `(household_id, idempotency_key)` e cada registro associa a chave
pública, o fingerprint exato da requisição e a decisão imutável devolvida. Mais
de uma chave logicamente equivalente pode apontar para a mesma decisão
deduplicada. O replay da mesma chave e dos mesmos inputs devolve a decisão
original; reutilizar a chave com inputs diferentes retorna conflito HTTP 409.
UPDATE, DELETE e TRUNCATE do ledger são rejeitados pelo PostgreSQL.

As gravações de entradas financeiras marcam o household como
`REEVALUATION_REQUIRED` dentro da mesma transação. O scheduler é reconciliação,
não a única fonte de eventos.

## Scheduler e failure isolation

O job reutiliza Celery, Redis, a fila `intelligence` e Celery Beat existentes.
A cadência diária ocorre depois dos jobs de score, guardrails, tendência e
alertas de investimento. Ela usa `FRESHNESS` para reavaliar a cadeia completa,
pois a passagem do tempo pode tornar tanto o Financial State quanto dados de
mercado stale. Gravações financeiras marcam a categoria exata. Não há polling
subminuto ou scheduler paralelo.

O ciclo é bounded e processa households isoladamente. Uma falha não interrompe
os demais. Falha parcial de mercado é preservada como warning quando A4 puder
continuar com classes válidas; falha que torna a decisão insegura bloqueia a
nova cadeia sem apagar o último plano válido.

## Segurança e household

Todos os endpoints exigem autenticação e membership ativa, retornam 404
defensivo para acesso cruzado e `Cache-Control: private, no-store`. IDs de
households distintos não podem formar uma cadeia. O payload retornado pelo
backend já respeita ownership; o React não tenta inferir autorização.

Em households compartilhados, a decisão canônica permanece congelada, mas a
resposta é projetada para o usuário autenticado. Mudanças e ações `PERSONAL`
somente são exibidas ao owner. A projeção verifica os valores anterior e atual
do ownership, impedindo que uma transição como `PERSONAL B -> HOUSEHOLD` revele
o valor pessoal anterior ao membro A.

Quando existem elementos ocultos, status, materialidade, categorias, escopo e
alerta são recalculados apenas com as mudanças visíveis. Deltas agregados e
mensagens sem ownership verificável são tratados defensivamente, sem modificar
o payload imutável persistido. Alertas aplicam a mesma projeção por destinatário
e calculam materialidade local; destinatários sem mudanças visíveis, ou apenas
com materialidade `LOW`, não recebem alerta.

## API

```text
GET  /api/v1/financial/households/{id}/continuous-autopilot
POST /api/v1/financial/households/{id}/continuous-autopilot/evaluate
GET  /api/v1/financial/households/{id}/continuous-autopilot/history
GET  /api/v1/financial/households/{id}/continuous-autopilot/history/{decision_id}
```

O POST usa `Idempotency-Key` e é protegido por membership, lock por household,
dirty gate e dedupe. O cliente não controla `as_of` nem categorias: o endpoint
usa o relógio do servidor, enquanto Celery e testes injetam tempo apenas pela
fronteira interna. O namespace `continuous-scheduled:*` é reservado ao Beat.
Se o estado já estiver limpo, a chamada manual devolve o status corrente sem
reexecutar A1→A5.

Após uma avaliação técnica terminar em `FAILED`, novas chaves de avaliação
manual entram em cooldown por 60 segundos. Nesse período, a API responde HTTP
429 com `Retry-After` dinâmico. Replays idempotentes exatos são resolvidos antes
desse gate; execuções internas com `as_of`/categorias explícitas e o scheduler
não são limitados pelo cooldown. Os 60 segundos pertencem ao ruleset versionado.

## Migration e downgrade

No downgrade da migration `0023`, registros parciais A4/A5 produzidos por
reavaliações `INVESTMENT_CHAIN` são identificados antes da remoção do ledger
A6. Uma tabela temporária captura os IDs exatos de Action Plan e Investment
Orchestration pela cadeia relacional, validando allocation e versões dos
engines.

A remoção ocorre na ordem de dependência, primeiro A5 e depois A4. Chaves
públicas de idempotência, seus textos ou prefixos nunca são usados como prova
de proveniência. Decisões A4/A5 não demonstradas pela cadeia A6 permanecem
preservadas.

## Frontend

A área **Seu Autopilot** mostra se o plano está atualizado, mudou, requer ação
ou depende de informações. A timeline vem das decisões A6 congeladas; não é uma
segunda inbox. O detalhe mostra diff estruturado e CTAs seguros para o novo
plano, atualização de informações ou `/investir`. Nenhuma regra de materialidade
fica no React e nenhum CTA executa uma movimentação.

## Observabilidade

Estados e contadores persistidos, somados a logs estruturados, permitem medir
avaliações, mudanças, alertas, no-change e falhas. Logs contêm IDs técnicos,
materialidade e contagens, mas nunca renda, dívida, patrimônio, payload
financeiro completo, token ou secret. `NO_CHANGE` não é contabilizado como
falha.

## Limites da V1

- não executa ações financeiras;
- não adiciona provedor externo de notificação;
- não cria coletor de mercado;
- não apaga nem compacta histórico;
- não integra Trading V2;
- não implementa broker, Open Finance, PIX, PWA ou hardening de deployment.

Uma política futura de archival pode ser adicionada se o volume histórico
exigir, sem alterar decisões já congeladas.

# Fase 37 — Alertas, Monitoramento e Automação de Oportunidades

## Resultado

A Fase 37 adiciona acompanhamento contínuo às decisões auditadas do VinanceOS sem executar ordens e sem alterar Recommendation Engine, Budget Advisor, scores, guardrails, ML, trading ou snapshots históricos.

O fluxo implementado é:

```text
decisão auditada do usuário
→ subscription do ativo
→ Celery Beat
→ Budget Advisor oficial
→ nova decisão auditada pela Fase 35
→ comparação com o estado anterior
→ regras + thresholds
→ cooldown + deduplicação
→ alerta IN_APP
→ inbox autenticada
```

## Arquitetura

O módulo `backend/app/investment_alerts/` separa as responsabilidades em:

- `models.py`: subscriptions, estado técnico e alertas imutáveis;
- `schemas.py`: contratos autenticados, preferências, paginação, detalhe e métricas;
- `repository.py`: queries com ownership, locks, paginação, filtros e inserts idempotentes;
- `rules.py`: defaults, limites, vocabulário, prioridades e severidades;
- `evaluator.py`: comparação de snapshots, eventos, cooldown e chaves determinísticas;
- `service.py`: subscriptions, fluxo oficial de recomendação, auditoria Fase 35 e isolamento por ativo;
- `router.py`: endpoints REST autenticados;
- `tasks.py`: tarefa Celery e execução assíncrona segura.

Não foi criado scheduler paralelo. A infraestrutura existente de PostgreSQL, Redis, Celery worker e Celery Beat foi reutilizada.

## Migration e tabelas

A migration aditiva `0017_create_investment_alerts.py` parte de `0016_decision_performance` e cria três tabelas.

### `investment_alert_subscriptions`

Registra:

- owner (`user_id`);
- ativo e contexto congelado da consulta (`asset`, `market`, `budget`, `investor_profile`);
- decisão auditada de origem (`source_decision_id`);
- status ativo/pausado;
- cinco preferências de evento;
- thresholds de score e confiança;
- cooldown;
- versão da regra;
- timestamps.

Há unique em `(user_id, asset)`, checks de threshold/cooldown e FKs `RESTRICT` para usuário e decisão da Fase 35.

O browser envia apenas `asset` e `source_decision_id`. Score, ação, risco, orçamento e perfil não são aceitos como fonte de verdade do frontend; o backend os deriva de uma decisão Fase 35 pertencente ao usuário.

### `investment_alert_states`

Mantém o último estado técnico por usuário + ativo:

- `last_decision_id`;
- ação, score, confiança, risco e tendência anteriores;
- `last_checked_at`;
- `last_evaluation_key`;
- contadores operacionais.

Esse estado é bloqueado com `SELECT ... FOR UPDATE` durante a avaliação. Ele não substitui nem modifica a auditoria da Fase 35.

### `investment_alerts`

Persiste alertas históricos com:

- `alert_id` UUID;
- `deduplication_key` SHA-256 único;
- owner e subscription;
- `decision_id` da nova decisão Fase 35;
- ativo, tipo, severidade e canal `IN_APP`;
- snapshots JSON anterior e atual;
- mensagem factual;
- versão da regra;
- criação e leitura.

Alertas permanecem imutáveis, exceto `read_at`. A exclusão de uma subscription usa `SET NULL` no alerta e preserva o histórico; o estado técnico da subscription usa `CASCADE`.

## Integração com as Fases 35 e 36

Cada avaliação chama diretamente `build_explained_budget_recommendations()`, o mesmo fluxo oficial usado pelo Budget Advisor. O ativo monitorado é localizado no resultado calculado sem recalcular ou modificar score, guardrail ou decisão financeira.

Depois disso:

1. o payload derivado seleciona o ativo monitorado;
2. `build_decision_audit()` captura inputs, scores, guardrails, explicação e versões;
3. a decisão é persistida pelo repositório da Fase 35;
4. o avaliador compara exclusivamente o snapshot auditado persistido;
5. a Fase 36 poderá medir essa decisão quando seus horizontes amadurecerem.

Uma ausência real do ativo no ranking é auditada como `EMPTY/NO_RECOMMENDATION`; o sistema não fabrica `AVOID`, score ou confiança.

## Idempotência e concorrência

A avaliação usa uma chave determinística por:

```text
rule_version + subscription_id + data UTC
```

`decision_id` e `correlation_id` são UUIDv5 derivados dessa chave. Assim:

- retry da mesma execução reutiliza a mesma decisão auditada;
- dois workers são serializados pelo lock do estado;
- crash depois da auditoria e antes do alerta reaproveita a auditoria existente;
- uma nova janela diária gera novo `decision_id`;
- uma nova consulta manual continua gerando decisão independente.

Cada ocorrência de alerta recebe SHA-256 determinístico com subscription, tipo, decisão anterior e transição material. O insert PostgreSQL usa `ON CONFLICT DO NOTHING` sobre a chave única. Retry, dois workers, chamada duplicada e reexecução da mesma ocorrência produzem no máximo um alerta equivalente.

Exemplos exclusivamente de fixture, sem dados pessoais:

- `decision_id`: `37000000-0000-4000-8000-000000000099`
- `correlation_id`: `37000000-0000-4000-8000-000000000002`

## Regras de detecção

### Mudança de ação

São observadas as seis transições entre `BUY`, `WAIT` e `AVOID`. Transições para `BUY` têm prioridade.

### Nova oportunidade

`WAIT → BUY`, `AVOID → BUY` ou um `BUY` novo sem `BUY` anterior são classificados como `NEW_OPPORTUNITY`. Quando essa preferência está ativa, não é emitido um segundo `ACTION_CHANGE` equivalente.

### Score e confiança

- delta mínimo de score: 5 pontos;
- delta mínimo de confiança: 10 pontos;
- comparação: `abs(atual - anterior) >= threshold`;
- confiança ausente é ausência legítima e não gera valor nem alerta fictício.

### Risco

São comparadas apenas as categorias reais `LOW`, `MEDIUM`, `HIGH` e `UNKNOWN`.

## Severidade

- `HIGH`: nova oportunidade, `BUY → AVOID` e aumento para risco alto;
- `MEDIUM`: `BUY → WAIT`, mudanças relevantes de score/confiança e aumento moderado de risco;
- `INFO`: demais transições e redução de risco.

As mensagens são factuais. Não são usados “compre agora”, “lucro garantido”, “oportunidade certa” ou “venda imediatamente”.

## Cooldown e limites

- cooldown default: 180 minutos;
- cooldown mínimo: 30 minutos;
- cooldown máximo: 10.080 minutos;
- uma ocorrência idêntica continua deduplicada;
- um evento `HIGH` materialmente diferente pode ultrapassar o cooldown;
- mesmo quando um alerta é suprimido, o estado monitorado é atualizado.

Limites operacionais:

- 20 subscriptions ativas por usuário;
- 500 subscriptions por ciclo;
- 4 alertas por avaliação de subscription;
- 100 alertas por ciclo;
- recommendation limit interno de 100 para localizar o ativo monitorado.

## Celery

A tarefa registrada é:

```text
investment_alerts.evaluate_subscriptions
```

Ela utiliza a fila `intelligence`. O Beat executa diariamente às 22:10, após scores (21:35), guardrails (21:45) e tendências (21:55). A frequência diária evita gerar até 48 snapshots idênticos por ativo quando as fontes técnicas relevantes só são atualizadas uma vez ao dia.

Falha em uma subscription incrementa seu contador operacional e não interrompe as demais.

Uma execução real do task no Docker, com banco sem subscriptions, concluiu em cerca de 0,12 s com zero avaliações, zero alertas e zero erros.

## APIs autenticadas

```text
GET    /api/v1/investments/alert-subscriptions
POST   /api/v1/investments/alert-subscriptions
PATCH  /api/v1/investments/alert-subscriptions/{subscription_id}
DELETE /api/v1/investments/alert-subscriptions/{subscription_id}

GET    /api/v1/investments/alerts
GET    /api/v1/investments/alerts/{alert_id}
PATCH  /api/v1/investments/alerts/{alert_id}/read
GET    /api/v1/investments/alerts/metrics
```

O inbox aceita paginação, ativo, tipo, severidade, não lidos e período. IDs inválidos, inexistentes e pertencentes a outro usuário retornam resposta indistinguível de não encontrado.

## Frontend

Na tela `/investir` foram adicionados:

- `InvestmentMonitoringControl`: ativa, pausa, reativa, configura e exclui monitoramento do ativo da decisão atual;
- `InvestmentAlertsPanel`: inbox recolhível com contador, filtros, paginação e estados vazios;
- detalhe comparativo com recomendação, score, confiança e risco antes/agora;
- vínculo discreto ao `decision_id` relacionado;
- tratamento de loading, API indisponível e sessão expirada;
- layout responsivo, inclusive modal com rolagem interna em telas de 320 px.

A experiência principal continua focada na decisão; os controles técnicos permanecem secundários e nenhum painel de trading foi criado.

## Segurança

Foram validados:

- anônimo e token inválido recebem 401;
- queries, updates, delete e read combinam identificador com `user_id`;
- usuário A não lê nem marca alerta do usuário B;
- usuário A não altera subscription do usuário B;
- filtros possuem vocabulário/regex e queries parametrizadas;
- payload extra com score, ação ou risco é rejeitado;
- snapshots passam pela sanitização da Fase 35;
- logs redigem Bearer tokens e não persistem senha, cookie, header de autorização, refresh token, API key ou segredo.

## Observabilidade

Logs estruturados JSON carregam, quando aplicável:

- `user_id`;
- `asset`;
- `subscription_id`;
- `decision_id`;
- `alert_id`;
- `alert_type`;
- `severity`;
- `status`;
- contagens do ciclo.

O formatter estruturado e sua política de redação também foram ligados ao worker e ao Beat.

Métricas simples disponíveis:

- subscriptions ativas;
- avaliações realizadas;
- alertas gerados;
- supressões por cooldown;
- duplicados evitados;
- supressões por volume;
- erros;
- não lidos;
- distribuição por tipo.

## Validações realizadas

### Backend

- Fases 34–37: 179/179;
- testes específicos da Fase 37: 99/99;
- Recommendation Engine ampliado: 106/106;
- Fases 22–31: 48/48;
- `emergency_reserve_priority`/Intelligence Base: 12/12.

### Frontend

- testes Node de decisão: 8/8;
- testes Vitest: 59/59;
- total frontend: 67/67;
- E2E Chromium: 10/10;
- lint: aprovado;
- typecheck da aplicação e testes: aprovado;
- Vite build: aprovado, 1.684 módulos transformados.

Total da matriz relevante sem duplicar testes: 362/362.

### Docker e banco

- migration atual: `0017_investment_alerts (head)`;
- backend saudável;
- frontend servindo `/login` e `/investir` com HTTP 200;
- PostgreSQL e Redis saudáveis;
- Celery worker registrando a task da Fase 37;
- Celery Beat carregando o schedule;
- endpoints anônimos de subscription/alertas retornando 401;
- constraints, índices e FKs inspecionados no PostgreSQL.

## Dados reais encontrados

Após a migration e as validações:

- subscriptions reais: 0;
- estados monitorados reais: 0;
- alertas reais: 0;
- decisões Fase 35 reais: 0;
- avaliações Fase 36 reais: 0.

Não havia dados reais suficientes para observar mudança de recomendação. Nenhuma atividade foi fabricada no banco. Os cenários de transição foram validados somente com fixtures/overrides isolados.

## Limitações conhecidas

- a cadência é diária enquanto as fontes centrais permanecerem diárias;
- canais externos (WhatsApp, SMS, Telegram, push) não fazem parte desta fase;
- métricas acumuladas do estado técnico deixam de existir quando a subscription é excluída, embora os alertas históricos permaneçam;
- o worker Docker já operava como root e continua emitindo o aviso padrão do Celery; alterar o usuário do container ficou fora do escopo funcional desta fase;
- o navegador integrado do ambiente não estava conectado para inspeção manual adicional; Chromium/Playwright cobriu a renderização real e a ausência de overflow;
- a suíte global legada ainda contém dois módulos antigos com imports removidos (`SessionLocal` e `FinancialDecisionHistory`), fora da matriz financeira e das Fases 34–37. Eles não foram alterados para obter verde.

## Readiness

A Fase 37 está pronta no escopo solicitado:

```text
subscription
→ avaliação periódica
→ decisão Fase 35
→ comparação
→ evento relevante
→ cooldown/deduplicação
→ alerta IN_APP
→ usuário autenticado
→ histórico preservado
```

Nenhuma ordem é executada e nenhuma lógica financeira existente foi modificada.

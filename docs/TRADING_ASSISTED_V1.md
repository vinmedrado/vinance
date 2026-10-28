# Trading Assistido V1

## Contrato de produto

Trading Assistido é uma experiência de aprendizado e avaliação baseada na
engine Trading V2 já existente. Todo o fluxo é `PAPER_ONLY`. Não há broker,
ordem real, chave de execução, dispatch de capital nem escrita no patrimônio.

A conta Paper pertence ao usuário autenticado e possui escopo fixo
`PERSONAL`. `owner_user_id` vem da sessão. `HOUSEHOLD` é rejeitado em escrita e
o papel administrativo OWNER não cria bypass. O household escolhido na tela
serve apenas para ler, sob as projeções de privacidade existentes, o contexto
financeiro usado pelo risk budget.

## Fluxo reutilizado

```text
Market Data → Feature Store → Prediction Engine → Validation V2
            → Model Registry → sinal Paper atual → operação simulada
```

Prediction, targets, custos, slippage, `PaperRiskManager`, backtests, Research
e Validation permanecem as implementações canônicas. A camada de produto
acrescenta persistência, ownership, API, orquestração explícita e UX.

## Schema externo

O schema Trading não pertence ao Alembic principal. O lifecycle próprio é:

```bash
python -m backend.trading.storage.migrate status
python -m backend.trading.storage.migrate upgrade
python -m backend.trading.storage.migrate check
```

Rollback é destrutivo e deve ocorrer somente em banco isolado validado:

```bash
python -m backend.trading.storage.migrate rollback --allow-destructive
```

Ao reverter `0002`, os estados novos de sinal são reduzidos à semântica
legada (`BUY_CANDIDATE → BUY`, `AVOID → HOLD`) antes de restaurar o campo
`VARCHAR(10)`. Essa perda deliberada de granularidade é mais um motivo para
nunca executar o rollback destrutivo no banco canônico sem backup e plano de
recuperação.

As revisões atuais são:

- `0001_initial_research` — candles, features, targets, sinais, backtests e
  estruturas históricas de pesquisa;
- `0002_assisted_paper_v1` — contas, ordens, posições, event store e campos
  operacionais dos sinais.

O runner guarda checksum/histórico, usa advisory lock, aplica upgrades dentro
de transação e falha fechado em drift ou versão incompatível. O serviço
`migrate` do Compose de produção executa primeiro o Alembic principal e depois
o runner externo; web, worker e Beat dependem desse gate único.

## Backup e restore

O utilitário cria dump custom **data-only** apenas das tabelas Trading e nunca
sobrescreve um arquivo existente:

```bash
python -m backend.trading.storage.backup backup caminho/trading.dump
python -m backend.trading.storage.backup validate caminho/trading.dump
```

Ele exige entradas `TABLE DATA`, gera SHA-256 e não inclui users/households.
Depois do primeiro uso, porém, contas, ordens, posições, P&L e eventos Paper
são dados pessoais: o dump deve receber ACL restrita e criptografia antes de
sair do host. Em produção, o backup completo criptografado do runbook é o
artefato canônico para recuperar também funções, triggers e índices. Restore
data-only só aceita target isolado, schema compatível e tabelas Trading vazias:

```bash
python -m backend.trading.storage.backup restore caminho/trading.dump \
  --confirm-isolated-target
```

## Persistência Paper

- `trading_paper_accounts`: uma conta ativa por usuário, `PERSONAL`, USDT,
  saldo virtual e `paper_only=true` por constraint;
- `trading_paper_orders`: idempotência por conta, fingerprint da request,
  ownership composto e snapshot de risco/decisões;
- `trading_paper_positions`: posição LONG simulada, ordens de abertura/fecho,
  P&L e optimistic version;
- `trading_paper_events`: trilha append-only de conta, risk check, ordem,
  posição e fechamento.

Toda operação usa transação. Constraints compostas impedem ligar registros de
owners diferentes; locks e índices únicos impedem double fill e repetição de
idempotency key.

## Risk budget e capital protegido

`TradingRiskBudget` lê A1→A6 sem modificar suas decisões. Na V1:

```text
real_trading_allowed = false
real_trading_capital = 0
speculative_capital = 0
trading_dispatch = false
```

Reserva, dívida, objetivos, patrimônio e investment bucket não viram saldo
executável. Dados incompletos podem bloquear capital real, mas não impedem o
aprendizado com saldo virtual.

## Model registry e promoção

O manifest versionado guarda identidade, versões de feature/target, checksum,
período de treino, métricas e status:

```text
RESEARCH → VALIDATED → PAPER_CANDIDATE → PAPER_ACTIVE
                    ↘ REJECTED / RETIRED
```

`PAPER_ACTIVE` exige evidência de Validation V2 com
`paper_trading_ready=true`. A promoção fixa o checksum do artefato; toda leitura
de modelo promovido recalcula e compara esse valor, inclusive com cache aquecido.
Artefato ausente, trocado, corrompido ou referência sem evidência falha fechado.
Pesquisa não é promovida só por existir no disco.

## Orquestração manual

O serviço `paper_orchestration` reutiliza o artefato exato aprovado no registry
e o Prediction Engine. Ele valida preço positivo, versões, freshness e
guardrails; persiste um sinal idempotente por `prediction_id`; não cria ordem.

```bash
python -m backend.trading.paper_orchestration.cli status
python -m backend.trading.paper_orchestration.cli run-once
```

Não há task Celery nem agenda Beat para Trading nesta versão.

## API e frontend

Todas as rotas usam autenticação. Escritas Paper filtram pelo usuário da sessão:

- overview e risk budget;
- oportunidades e sinais paginados;
- conta, ordens, posições e eventos owner-only;
- backtests válidos e model registry público ao usuário autenticado;
- health específico do domínio.

A rota `/trading` fica no menu secundário para preservar cinco destinos na
bottom navigation. A interface mostra permanentemente “PAPER ONLY”, usa USDT
como saldo virtual, não inventa confidence/oportunidade e informa quando
Validation V2 ainda não liberou modelos.

## Assistente financeiro

O contexto enviado ao provider é estruturado e allowlisted: risk budget,
resumo da conta Paper, posições, P&L, drawdown, oportunidades atuais, modelos,
eventos recentes e resumos de backtests. Não são enviados tabelas completas,
artefatos, secrets ou Paper de outro usuário. O prompt separa dados do Vinance
de interpretação e proíbe linguagem de certeza ou execução real.

## Próximo gate: scheduler Paper

Antes de autorizar automação contínua ainda é necessário:

1. promover manualmente um modelo validado para `PAPER_ACTIVE`;
2. definir/promover dados de runtime canônicos;
3. validar freshness e latência na infraestrutura de produção;
4. implementar marcação periódica/recovery observável;
5. aprovar explicitamente uma task idempotente e uma agenda única;
6. manter `live_trading_ready=false` e `TRADING_REAL=false`.

# Financial Policy v1

`financial-policy-v1` transforma o resultado canônico de
`household-financial-state-v1` em uma ordem prudencial de prioridades. Ele não
seleciona ativos, mercados, produtos, percentuais de alocação nem quantidades.

## Contrato e determinismo

A decisão recebe três entradas:

1. o Financial State atual;
2. os mesmos inputs normalizados que originaram esse State;
3. opcionalmente, um Financial State anterior reconstruído de snapshot.

O engine não consulta banco, relógio, Recommendation Engine ou Trading. O
timestamp de avaliação vem do Financial State. O fingerprint de decisão cobre o
payload decisório produzido (estado, gates, prioridades, evidências e traces),
enquanto IDs de snapshot permanecem metadados de auditoria. Assim, snapshots
materialmente idênticos mantêm a mesma decisão.

O contexto normalizado é obrigatório para avaliar ownership, moedas, taxas e
vencimentos. Um contexto ausente ou pertencente a outro household bloqueia a
política. Registros `PERSONAL` só são considerados para membros ativos; registros
`HOUSEHOLD` permanecem válidos quando registrados por um membro conhecido que
depois foi removido, exatamente como no State v1.

## Precedência dos estados

A primeira condição aplicável define o estado principal:

1. `DATA_BLOCKED`
2. `CASHFLOW_RECOVERY`
3. `DEBT_PRIORITY`
4. `EMERGENCY_RESERVE_PRIORITY`
5. `GOAL_PRIORITY`
6. `INVESTMENT_READY`, quando todos os gates passam
7. `BALANCED_BUILD`, nos demais casos seguros porém limitados

A prontidão para capital novo é independente do label principal e assume
`BLOCKED`, `LIMITED` ou `READY`. Ela não é recomendação de investimento.

## Regras congeladas em `financial-policy-rules-v1`

| Regra | Valor v1 | Efeito |
|---|---:|---|
| Confidence mínimo para política | 50 | Abaixo disso, `DATA_BLOCKED` |
| Confidence mínimo para `READY` | 85 | Abaixo disso, no máximo `LIMITED` |
| Serviço da dívida prioritário | 20% da renda recorrente | `DEBT_PRIORITY` |
| Serviço da dívida bloqueante | 30% da renda recorrente | prontidão `BLOCKED` |
| DTI de alerta | 50% da renda recorrente anual | warning, sem bloqueio isolado |
| Custo anual conhecido elevado | 15% | prioridade e bloqueio de novos aportes |
| Horizonte de vencimento de dívida | 90 dias | prioridade, sem presumir default |
| Piso prudencial de reserva | 3 meses | ponto de partida, nunca alvo universal final |
| Teto de reserva v1 | 6 meses | limite dos ajustes conhecidos |
| Pressão de despesas fixas | 70% das despesas | adiciona 1 mês |
| Pressão de serviço da dívida | 20% da renda recorrente | adiciona 1 mês |
| Dependência de renda não recorrente | 20% da renda total | adiciona 1 mês |
| Objetivo urgente | até 90 dias | prioridade quando há funding gap |
| Objetivo próximo HIGH/MEDIUM | até 365 dias | prioridade quando há funding gap |

Os valores, a precedência, os campos críticos e as moedas suportadas vivem em
`backend/app/financial_policy/rules.py` e participam do fingerprint do ruleset. Toda regra
executada registra ID, versão, valores observados, thresholds, outcome e
explicação. Outcomes usam apenas `TRIGGERED`, `NOT_TRIGGERED` e
`NOT_EVALUATED`.

## Data gate

`INSUFFICIENT`, `INCONSISTENT`, inconsistências explícitas, confidence inválido ou
abaixo de 50, campos críticos de renda/caixa ausentes, renda/despesa stale,
contexto ausente ou divergente e agregação monetária sem moeda comparável geram
`DATA_BLOCKED`.

Dados secundários ausentes podem permitir uma ordem limitada, mas nunca
`READY`. Entre eles estão capacidade de investimento, patrimônio, passivos,
reserva, serviço da dívida, progresso/prazo de objetivos e taxa de dívida ativa.

`None` significa desconhecido. O número `0` é um valor real: reserva zero gera
`ABSENT`; capacidade zero exige recuperação; ausência desses campos não recebe
zero implícito. Moeda ausente também não recebe `BRL` implícito para patrimônio,
passivos ou objetivos. Esta versão não converte câmbio.

## Caixa, passivos, reserva e objetivos

Fluxo disponível, disposable income ou savings capacity não positivos precedem
qualquer aporte. Quando existe snapshot anterior comparável, a transição de um
valor positivo para não positivo é registrada como deterioração. Sem histórico,
o engine declara a limitação e não inventa tendência.

Dívidas são ordenadas por default explícito, custo conhecido, pressão mensal e
vencimento conhecido. Taxa ausente permanece `UNKNOWN_COST`; vencimento passado
com status `ACTIVE` recebe atenção, mas nunca é convertido em `DEFAULTED`.
Patrimônio líquido negativo prioriza redução de passivos sem virar bloqueio duro
isoladamente.

O alvo de reserva parte de um piso prudencial versionado de três meses e só
recebe os ajustes cujo contexto pode ser calculado; portanto, não aplica a mesma
quantidade fixa a todos. Se algum modificador v1 estiver desconhecido, a saída usa
`ADEQUATE_FOR_KNOWN_CONTEXT` e limita a prontidão. Estabilidade profissional,
dependentes e outras responsabilidades ainda não existem no modelo; aparecem
como dimensões não modeladas e limitações, não como suposições. A saída expõe o
método, os modificadores e confirma que nenhum alvo universal foi aplicado.

Objetivos usam funding gap, prioridade declarada e deadline conhecido. Quando
gap, prazo e capacidade pós-serviço da dívida são conhecidos, a política calcula
o funding mensal requerido em janelas versionadas de 30 dias e sinaliza quando
ele excede a capacidade; ausência de qualquer entrada deixa a viabilidade como
desconhecida. Um goal
`HIGH` subfinanciado pode ser prioritário sem deadline; goals `LOW` ou `MEDIUM`
subfinanciados sem deadline limitam prontidão porque prazo ausente não significa
infinito. Objetivo integralmente financiado não é limitado só por não ter prazo.

## Auditoria e APIs

- `GET /api/v1/financial/households/{household_id}/financial-policy`
- `GET /api/v1/financial/households/{household_id}/financial-policy/from-state-snapshot/{snapshot_id}`

As duas rotas exigem autenticação, aplicam o isolamento do household e usam
`Cache-Control: private, no-store`. A segunda reconstrói o State a partir do
snapshot imutável existente, valida o fingerprint dos inputs e compara o contrato
persistido ao State reconstruído antes de reaplicar as regras congeladas. Falhas
de integridade fecham o replay. Assim, não há segunda tabela de snapshot nem
migration nesta fase. O serviço é somente leitura e não chama `commit`,
`create_all` ou um segundo engine/Base. No cliente, as chaves de cache financeiro
são vinculadas à sessão para não reutilizar dados entre identidades.

As tabelas externas do Trading V2 continuam fora do ownership do Alembic e não
são lidas ou alteradas pelo Financial Policy Engine.

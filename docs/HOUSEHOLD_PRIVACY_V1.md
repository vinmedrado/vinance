# Household Privacy V1

## Objetivo

Este documento define o contrato canônico de privacidade financeira entre membros de um household. Ele se aplica a receitas, despesas, dívidas, patrimônio, objetivos e às decisões do Financial Autopilot.

## Escopos de ownership

### `PERSONAL`

Um registro `PERSONAL` é privado do `owner_user_id` (o `user_id` canônico do registro):

- somente o proprietário pode listar, consultar, alterar ou excluir o registro;
- o proprietário é derivado da sessão autenticada na criação e não pode ser escolhido pelo cliente;
- conhecer o ID do registro não concede acesso; a API responde como recurso inexistente (`404`) para outro usuário;
- ser `OWNER` do household não concede bypass sobre dados pessoais de outro membro;
- somente o proprietário pode compartilhar explicitamente o registro ao mudar o escopo para `HOUSEHOLD`.

### `HOUSEHOLD`

Um registro `HOUSEHOLD` foi compartilhado explicitamente:

- membros ativos do household podem lê-lo;
- mutações seguem as permissões compartilhadas existentes (criador do registro ou `OWNER`, conforme o contrato do serviço);
- nenhum rateio implícito entre membros é criado;
- mudar um registro compartilhado para `PERSONAL` não transfere sua propriedade: somente o proprietário original pode fazer essa mudança.

`created_by` registra autoria quando aplicável. Ele não substitui `owner_user_id`.

## Visões privadas e compartilhadas

Uma visão privada de um household `PERSONAL` usa os registros pessoais do usuário autenticado e registros explicitamente compartilhados naquele contexto.

Uma visão compartilhada de um household `SHARED` usa **somente** registros cujo `ownership_scope` seja `HOUSEHOLD`. Dados `PERSONAL` de membros não entram em:

- métricas ou totais compartilhados;
- `member_views`;
- evidências, inconsistências ou campos ausentes compartilhados;
- snapshots;
- Policy, Allocation, Orchestration, Action Plan ou Continuous Autopilot;
- alertas ou históricos compartilhados.

Isso evita vazamento direto e também inferência por subtração. Por exemplo, uma renda pessoal não pode ser deduzida de um total consolidado visível ao outro membro.

Novos inputs e estados registram:

- `privacy_contract_version = household-privacy-v1`;
- `decision_scope = PERSONAL` ou `HOUSEHOLD_SHARED`.

Snapshots históricos permanecem imutáveis. O baseline da adoção deste contrato não possuía decisões históricas de households compartilhados, portanto nenhuma decisão congelada precisou ser reescrita.

## Financial Autopilot

No escopo `HOUSEHOLD_SHARED`, o fluxo A1→A6 recebe apenas o pool explicitamente compartilhado:

1. Financial State filtra todos os domínios e não produz visões pessoais de membros.
2. Financial Policy não recebe métricas individuais privadas.
3. Capital Allocation trata a capacidade compartilhada como pool do household, sem transferência implícita entre membros.
4. Investment Orchestrator usa somente patrimônio compartilhado; perfis de investidor continuam pessoais e, sem um perfil household explícito, o contexto compartilhado falha fechado como `MISSING`.
5. Action Plan herda apenas ações autorizadas pela cadeia compartilhada.
6. Continuous Autopilot não recebe marcador de alteração pessoal no household compartilhado e mantém projeção por destinatário nos alertas.

## Histórico e alertas

As mesmas regras de leitura valem para estado atual e histórico. Uma decisão compartilhada nova nunca congela dados pessoais de outro membro. Alertas `PERSONAL` são visíveis somente ao proprietário; alertas `HOUSEHOLD` podem ser exibidos a membros ativos autorizados.

## Segurança de mutations no frontend

Todo formulário financeiro captura um `form_context_household_id` quando é aberto. No submit, esse ID precisa continuar igual ao household selecionado.

- formulário limpo: a troca de household é imediata e o formulário é reiniciado;
- formulário com alterações: a troca exige confirmação explícita para descartar;
- mutation em andamento: o seletor fica bloqueado;
- troca de sessão: drafts e contextos são descartados;
- respostas e invalidações usam o household e o token capturados pela própria mutation, nunca o seletor atual;
- query keys financeiras incluem sessão e household, impedindo que o cache de A seja exibido em B.

O frontend ainda filtra defensivamente itens `PERSONAL` que não pertençam ao usuário armazenado na sessão. Essa camada não substitui a autorização do backend.

## Datas civis

Datas escolhidas pelo usuário em formulários usam o calendário local do browser. Elas não são derivadas de `toISOString()`, que converte para UTC e pode avançar o dia no horário de São Paulo. Timestamps de auditoria do backend continuam em UTC.

## Produto household

O lifecycle de household compartilhado usa convite com consentimento explícito. Criar um convite `PENDING` não cria membership ativa. Somente o usuário autenticado cujo e-mail normalizado corresponde ao convite pode aceitá-lo; recusa e cancelamento não concedem acesso. O household pessoal permanece separado e não aceita convites.

O frontend oferece CRUD canônico de receitas, despesas, dívidas, patrimônio e objetivos, além de edição do perfil financeiro pessoal. Novos registros começam como `PERSONAL`; a mudança para `HOUSEHOLD` exige intenção explícita e mantém as regras deste documento.

Perfil de investimento compartilhado e rateio automático continuam fora do contrato. A ausência dessas capacidades nunca autoriza o uso de dados pessoais de outro membro.

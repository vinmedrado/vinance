# Household Product V1

## Objetivo

O Household Product V1 permite que duas pessoas mantenham contas próprias e usem um household compartilhado sem abrir seus dados pessoais. Ele reutiliza o domínio financeiro e o contrato de privacidade canônicos; não cria um segundo sistema de renda, despesa, patrimônio ou Autopilot.

## Tipos de household

### Pessoal

O cadastro cria um household `PERSONAL` para o usuário. Ele:

- possui somente o próprio usuário como `OWNER` ativo;
- não aceita convites;
- continua existindo quando o usuário entra em um household compartilhado;
- é o fallback de contexto padrão quando o usuário sai ou é removido do contexto que estava marcado como padrão.

### Compartilhado

Um usuário pode criar um household `SHARED`. O criador entra como `OWNER`, com membership ativa, sem substituir automaticamente seu household pessoal nem alterar seu contexto padrão.

## Convites e consentimento

Adicionar uma pessoa é um processo explícito:

```text
OWNER cria convite PENDING para um e-mail normalizado
        ↓
usuário autenticado com o mesmo e-mail aceita ou recusa
        ↓
somente ACCEPT cria ou reativa a membership ACTIVE
```

Convites podem ter os estados `PENDING`, `ACCEPTED`, `DECLINED`, `CANCELLED` e `EXPIRED`. Um `OWNER` pode cancelar apenas convite pendente do próprio household. Convite repetido pendente para o mesmo household/e-mail é bloqueado. Expiração é persistida antes de permitir novo convite.

O aceite é transacional, idempotente e serializado no PostgreSQL. Retentativas não criam segunda membership. E-mail usa a mesma normalização da autenticação. Não existe envio externo de e-mail nesta versão; os convites aparecem na área **Casa e família** quando o convidado entra no Vinance.

## Papéis e lifecycle

Papéis V1:

- `OWNER`: administra household, convites, papéis e remoções;
- `MEMBER`: usa o contexto compartilhado sem permissão administrativa.

O papel administrativo nunca concede leitura de registros `PERSONAL` de outra pessoa.

Um household compartilhado deve manter ao menos um `OWNER` ativo. Locks por household serializam alterações de papel, remoção e saída; duas operações concorrentes não podem remover todos os owners. Um `MEMBER` pode sair. Um `OWNER` pode sair somente quando outro owner ativo permanece. Remover ou sair desativa a membership, preservando registros e decisões históricas.

Se a membership removida era o contexto padrão, o household pessoal volta a ser padrão. Remover uma membership que não era padrão não altera a escolha vigente do usuário.

## Household padrão

Cada usuário possui no máximo uma membership ativa marcada como padrão. A escolha é persistida no backend e restaurada após login/reload. Ela é individual: escolher um household padrão não altera a preferência de outro membro.

## Ownership financeiro

Os recursos canônicos são:

- receitas;
- despesas;
- dívidas/obrigações;
- patrimônio (`owned_assets`, distinto de `asset_catalog`);
- objetivos;
- perfil financeiro pessoal.

Novos registros começam como `PERSONAL`. O usuário pode escolher explicitamente compartilhar com o household. Somente o proprietário pode mudar o escopo. Um `OWNER` pode manter registro `HOUSEHOLD` criado por outro membro, mas não pode torná-lo pessoal nem acessar registros pessoais alheios.

O frontend oferece create, list, update e delete para os cinco recursos e create/update do perfil financeiro. Valores desconhecidos permanecem `null`; zero informado permanece zero. Datas opcionais não recebem prazo inventado. Moeda e status existentes são preservados em edições.

## Interação com o Autopilot

Mutações em household pessoal marcam apenas o contexto pessoal aplicável. Mutações em registros `HOUSEHOLD` marcam o household compartilhado para reavaliação. A cadeia A1→A6 compartilhada usa somente registros explicitamente compartilhados.

Membership aceita, mudança de papel, remoção e saída também marcam o household compartilhado como alterado. Dados financeiros não são transferidos, rateados ou apagados por essas operações.

## Segurança do frontend

Queries incluem sessão, household e recurso. Formulários capturam a sessão e o household ao abrir. A troca de household:

- ocorre diretamente quando não há rascunho;
- pede confirmação quando há alterações não salvas;
- fica bloqueada durante mutation;
- nunca move o rascunho para outro household.

Requests de leitura usam `AbortSignal`; uma resposta atrasada continua vinculada à chave do contexto original. Invalidações usam o household e a sessão capturados pela mutation. Troca de usuário descarta seleção, drafts e perfil em edição.

## API

Além dos endpoints financeiros existentes, a V1 expõe:

```text
POST /api/v1/financial/households
GET  /api/v1/financial/households/{id}/members
PATCH/DELETE /api/v1/financial/households/{id}/members/{member_id}

POST /api/v1/financial/households/{id}/invitations
GET  /api/v1/financial/households/{id}/invitations
POST /api/v1/financial/households/{id}/invitations/{invitation_id}/cancel

GET  /api/v1/financial/household-invitations
POST /api/v1/financial/household-invitations/{invitation_id}/accept
POST /api/v1/financial/household-invitations/{invitation_id}/decline

POST /api/v1/financial/households/{id}/default
POST /api/v1/financial/households/{id}/leave
```

Todos exigem autenticação. Recursos cross-household e convites destinados a outro usuário falham defensivamente. A ativação direta de membro sem convite/aceite não existe no contrato público.

## Limites explícitos

Esta versão não inclui provedor externo de e-mail, recuperação de senha, RBAC além de `OWNER`/`MEMBER`, rateio financeiro, perfil de investimento compartilhado, execução bancária ou execução de investimentos.

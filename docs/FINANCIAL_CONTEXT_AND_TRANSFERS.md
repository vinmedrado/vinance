# Contexto financeiro e transferência de lançamentos

## Contrato de produto

- `PERSONAL` aparece como **Minhas finanças** e permanece visível somente ao titular.
- `HOUSEHOLD` aparece como **Finanças do casal** e é visível aos membros ativos da conta compartilhada.
- O contexto ativo é o household canônico já existente; não há um segundo mecanismo de escopo.
- Receitas e despesas novas exigem destino explícito. O backend deriva o titular da sessão e valida tipo do household e membership.

## Transferência auditada

Somente receitas e despesas `PERSONAL` do usuário autenticado podem ser movidas para um household `SHARED` do qual ele seja membro ativo.

Rotas:

- `POST /api/v1/financial/households/{target_id}/expenses/transfer-from-personal/preview`
- `POST /api/v1/financial/households/{target_id}/expenses/transfer-from-personal`
- equivalentes para `incomes`

O commit exige `Idempotency-Key`, aceita de 1 a 100 IDs únicos e é atômico. O fluxo:

1. descobre a origem sem alterar dados;
2. bloqueia todos os households envolvidos em ordem crescente, depois o ator e, por fim, os registros financeiros;
3. relê a chave idempotente depois de qualquer espera por lock;
4. revalida ownership e membership;
5. detecta lançamentos semanticamente semelhantes sem excluí-los;
6. altera o mesmo registro de `PERSONAL` para `HOUSEHOLD`;
7. grava transferência, itens e imagem anterior para auditoria;
8. marca origem e destino para reavaliação A6;
9. confirma tudo em uma única transação.

A ordem de locks é a mesma dos fluxos de membership e foi validada contra remoção e saída concorrentes de um membro. A transferência falha fechada quando a membership deixa de ser válida; ela não produz fill parcial, item de auditoria órfão nem mudança de visibilidade incompleta.

Não existe transferência inversa nesta versão. Patrimônio, objetivos, dívidas, investimentos e Paper Trading não participam deste fluxo.

## Migração

A revisão `0028_financial_record_transfers` cria apenas as tabelas de auditoria:

- `financial_record_transfers`
- `financial_record_transfer_items`

Ela não move lançamentos existentes. Antes de publicação:

1. criar backup verificado do PostgreSQL;
2. executar `alembic upgrade head` em PostgreSQL temporário vazio;
3. executar os testes PostgreSQL isolados, incluindo concorrência;
4. revisar `alembic check`, upgrade e downgrade controlado;
5. aplicar `0028` em janela controlada;
6. publicar backend e frontend compatíveis juntos;
7. validar contagens pessoais, households e A1→A6.

O runbook específico da release está em `docs/FINANCIAL_CONTEXT_RELEASE_RUNBOOK.md`.

## Cache e decisões

Após uma transferência, o frontend invalida as consultas da origem e do destino para recursos financeiros e A1→A6. O backend marca ambos os contextos como `REEVALUATION_REQUIRED`; snapshots históricos permanecem imutáveis, mas não devem ser tratados como estado atual.

## Privacidade

- `owner_user_id` nunca é aceito do navegador.
- OWNER de household não recebe acesso a dados `PERSONAL` de outro membro.
- IDs de household fora da membership ativa falham fechado sem revelar existência.
- A prévia não grava dados.
- Nenhum lançamento real é transferido automaticamente; a pessoa escolhe os IDs e confirma a mudança de visibilidade.

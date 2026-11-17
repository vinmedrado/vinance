# Publicação da release de contexto financeiro

Este runbook publica somente o seletor **Minhas finanças / Finanças do casal**, o destino explícito de receitas e despesas e a transferência auditada `PERSONAL → HOUSEHOLD`.

## Invariantes

- Nenhum lançamento existente é transferido automaticamente.
- A revisão esperada antes da publicação é `0027_auth_sessions`; a revisão da release é `0028_financial_record_transfers`.
- A migration é aditiva: cria apenas as tabelas de auditoria e não reescreve receitas, despesas, usuários ou households.
- PostgreSQL e Redis não são recriados.
- O rollback da aplicação não executa downgrade do schema.
- `.env.production`, dumps, checksums, artifacts e dados não entram no Git.

## 1. Pré-flight somente leitura

1. Confirmar branch/commit aprovados e worktree limpo da release.
2. Executar `./deploy-production.ps1 validate`.
3. Confirmar `REGISTRATION_ENABLED=false` sem imprimir o arquivo de ambiente.
4. Registrar IDs dos containers e volumes de PostgreSQL/Redis.
5. Registrar apenas contagens das tabelas pessoais e de household usadas como invariantes; não exportar conteúdo.
6. Confirmar `alembic current = 0027_auth_sessions`, `alembic heads = 0028_financial_record_transfers` e ausência de qualquer outra revisão pendente.
7. Confirmar espaço suficiente para backup, imagens nova e anterior e restore temporário.

Se qualquer revisão além de `0028_financial_record_transfers` estiver pendente, interromper a publicação.

## 2. Backup e restore comprovado

1. Executar o serviço `backup` pelo profile `ops` conforme `docs/PRODUCTION_DEPLOYMENT_RUNBOOK.md`.
2. Exigir exit code zero, arquivo cifrado não vazio e checksum válido.
3. Verificar que o catálogo do dump contém schema, constraints, triggers, índices, `alembic_version` e `TABLE DATA`.
4. Restaurar em PostgreSQL temporário nominalmente isolado usando o script de restore existente.
5. No banco restaurado, comparar contagens de usuários, memberships, receitas, despesas, snapshots e decisões A1→A6 com o banco de origem.
6. Confirmar `alembic current = 0027_auth_sessions` no restore antes de continuar.

O banco canônico nunca é alvo do drill de restore.

## 3. Preservar rollback da aplicação

Antes do build, registrar os image IDs atuais de frontend, backend, Worker e Beat e aplicar tags locais imutáveis contendo o commit publicado anterior. Guardar também o Compose e o código correspondentes em um worktree de rollback. Não alterar volumes.

## 4. Migration explícita e deploy conjunto

1. Executar novamente `./deploy-production.ps1 validate`.
2. Executar `./deploy-production.ps1 all -ApplyMigrations`.
3. Conferir no prompt que o único salto é `0027_auth_sessions → 0028_financial_record_transfers` e confirmar conscientemente com `MIGRAR`.
4. O script deve aplicar a migration uma única vez e somente depois recriar backend, Worker, Beat e frontend. PostgreSQL e Redis precisam manter os mesmos container IDs.
5. Confirmar `alembic current = 0028_financial_record_transfers` e `alembic check` limpo.

Não executar migration implicitamente em múltiplos serviços e não usar `down`, `down -v` ou `prune`.

## 5. Smokes pós-publicação

- Todos os containers do stack ficam healthy; Beat de produção permanece ativo.
- `/health`, `/ready` e o edge local respondem HTTP 200.
- Login e sessão continuam válidos; registro público continua desabilitado.
- O seletor exibe o contexto ativo no desktop e no mobile.
- A troca de contexto atualiza os dados e descarta apenas rascunhos mediante confirmação.
- Cadastro de receita e despesa exige destino explícito e mostra a confirmação correta.
- Prévia de transferência funciona com uma conta de teste autorizada, sem confirmar uma transferência real durante o smoke.
- Usuário A não lê dados `PERSONAL` de B, mesmo sendo OWNER do household compartilhado.
- Mercado, Assistente e Trading PAPER_ONLY continuam acessíveis, sem mudanças funcionais.

Repetir as contagens pessoais e de household registradas no pré-flight. Até que uma pessoa confirme uma transferência na interface, todas devem permanecer idênticas.

## 6. Rollback seguro

Se houver regressão crítica:

1. interromper novas ações de transferência na aplicação;
2. restaurar somente as imagens da aplicação previamente etiquetadas;
3. manter PostgreSQL, Redis e seus volumes;
4. manter a revisão `0028`, pois ela é aditiva e o aplicativo anterior ignora as tabelas novas;
5. repetir health/readiness, autenticação e invariantes de contagem.

Não executar `alembic downgrade` em produção como mecanismo de rollback da aplicação. Restore do banco é último recurso e só pode ocorrer a partir do backup verificado, em procedimento separado e explicitamente autorizado.

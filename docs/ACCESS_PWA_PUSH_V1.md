# Access, PWA e Web Push V1

## Escopo

Esta versão adiciona cadastro controlado pelo navegador, administração de
acessos, instalação PWA e notificações Web Push. Ela não altera regras
financeiras, Autopilot, Mercado ou Trading.

Invariantes:

- `ACCESS_MODE=INVITE_ONLY`;
- `REGISTRATION_ENABLED=false`;
- convite da plataforma não concede acesso a household;
- `HOUSEHOLD OWNER` não é administrador da plataforma;
- cada nova conta recebe seu próprio household `PERSONAL`;
- nenhum endpoint financeiro é armazenado pelo service worker;
- a chave VAPID privada e o conteúdo completo das subscriptions permanecem no
  servidor;
- Trading permanece `PAPER_ONLY`.

## Bootstrap inicial

O primeiro administrador é criado pelo navegador, mas não pela regra insegura
“não existem usuários”. O backend exige simultaneamente:

1. estado singleton de bootstrap ainda pendente, bloqueado com `FOR UPDATE`;
2. banco ainda sem usuários;
3. credencial aleatória de uso único cujo SHA-256 está em
   `BOOTSTRAP_TOKEN_HASH`;
4. rate limit e validação de Origin.

A credencial bruta é gerada localmente por
`deploy/prepare-access-pwa-secrets.ps1` e gravada apenas em
`.private/bootstrap-credential.txt`, arquivo ignorado pelo Git e com ACL local
restrita. Ela deve ser digitada em `/access/bootstrap` e nunca compartilhada em
chat, logs ou commit. Depois do primeiro uso, o estado persistido fecha o fluxo
permanentemente; confirme o login e remova o arquivo bruto local de forma
controlada.

## Convites da plataforma

`Pessoas e acesso` permite ao administrador criar, rotacionar e cancelar
convites. Tokens são aleatórios, armazenados somente como hash, vinculados ao
e-mail, expiram e são de uso único. O link manual aparece somente na resposta
de criação ou reenvio.

Não existe automação Cloudflare nesta versão. O estado correto é
`PENDING_AUTHORIZATION` e a interface mostra “autorização de acesso pendente”.
O operador deve adicionar o e-mail à política restrita do Cloudflare Access
antes de entregar o convite. Não remover nem abrir a política global.

Também não existe provedor de e-mail configurado. A recuperação pública é
anti-enumeração, mas informa honestamente que o canal automático não está
disponível. Um administrador pode gerar um link manual de recuperação de uso
único. Concluir a redefinição revoga as sessões existentes.

## Administração e isolamento

`platform_admins` é independente de memberships de household. Todas as ações
administrativas usam a sessão autenticada como ator; o navegador não escolhe
`owner_user_id`. A desativação de uma conta revoga sessões e subscriptions
Web Push e suprime entregas pendentes.

O banco atual não utiliza RLS. O isolamento financeiro continua obrigatório na
camada de aplicação e é coberto por testes A/B. Como redução de privilégio, os
serviços de runtime usam uma role PostgreSQL própria com:

```text
NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
```

A role proprietária fica restrita ao serviço one-shot de migration. O gate de
deploy confirma a role declarada, o usuário embutido em
`RUNTIME_DATABASE_URL` e os privilégios efetivos antes de recriar a aplicação.

## PWA e política de cache

O manifesto usa `id=/`, `scope=/`, `display=standalone` e ícones próprios em
192, 512, maskable e Apple Touch. No Android/Chromium, “Instalar Vinance” usa o
evento nativo quando disponível. No iPhone/iPad, a interface apresenta o fluxo
real “Compartilhar → Adicionar à Tela de Início”; não promete instalação
programática.

O service worker aplica:

- `/api/*`: somente rede, nunca Cache Storage;
- assets versionados: cache estático;
- navegação offline: página neutra, sem valores ou dados antigos;
- `sw.js`, manifesto, offline e `index.html`: política HTTP de revalidação;
- atualização: ativação explícita pelo usuário, sem recarga silenciosa.

Se a sessão expirar, a aplicação volta ao login pelo fluxo normal. Trocar de
conta no mesmo dispositivo não transfere a subscription: o logout remove a
associação no backend e cancela a inscrição local.

## VAPID e subscriptions

As chaves P-256 são geradas localmente. Somente `VAPID_PUBLIC_KEY` é exposta
pela API autenticada. `VAPID_PRIVATE_KEY` e
`PUSH_SUBSCRIPTION_ENCRYPTION_KEY` são entregues apenas ao backend e ao Worker;
Beat, frontend e migrate não as recebem.

As subscriptions são vinculadas ao usuário autenticado e a uma instalação,
criptografadas com Fernet e identificadas no banco por hash de endpoint. O
servidor rejeita endpoints que não sejam HTTPS públicos e impede reassociação
silenciosa entre contas. Respostas 404/410 do push service expiram a inscrição.

Eventos inicialmente permitidos:

- convite para Finanças do casal;
- alerta financeiro realmente gerado;
- evento de conta genérico;
- análise nova quando o evento existir;
- notificação de teste solicitada pelo usuário.

Payloads são genéricos e não contêm saldos, valores, tokens ou senhas. Push de
Trading não é ativado.

### Rotação VAPID

Rotacionar a chave privada torna subscriptions existentes incompatíveis.
Procedimento:

1. desabilitar temporariamente `WEB_PUSH_ENABLED`;
2. gerar o novo par sem imprimir a chave privada;
3. revogar as subscriptions existentes;
4. publicar backend/worker/frontend com a nova chave pública;
5. reativar o envio;
6. cada dispositivo deve consentir e se inscrever novamente.

Não reutilizar a chave antiga depois da rotação.

## Validação em dispositivo real

Automação e emulação não comprovam Web Push no iOS. Antes de marcar como
validado em dispositivo real:

### Android

1. abrir o domínio HTTPS após autenticar no Cloudflare Access;
2. instalar pelo prompt nativo;
3. abrir em modo standalone;
4. ativar notificações em Configurações;
5. enviar notificação de teste;
6. testar com aplicação aberta, em segundo plano e fechada;
7. desativar e confirmar que novos envios não chegam.

### iPhone/iPad compatível

1. abrir no Safari;
2. Compartilhar → Adicionar à Tela de Início;
3. abrir o ícone instalado;
4. ativar notificações somente após o gesto explícito;
5. executar o mesmo teste aberto/segundo plano/fechado;
6. confirmar que o toque abre uma rota interna permitida e exige sessão válida.

## Publicação

Ordem segura:

1. gerar segredos no `.env.production` ignorado;
2. criar/validar a role PostgreSQL de runtime;
3. executar testes e migration `0029` em PostgreSQL isolado;
4. `./deploy-production.ps1 validate`;
5. aplicar a migration explicitamente pelo serviço `migrate`;
6. publicar backend e frontend juntos;
7. validar `/health`, `/ready`, capacidades, manifesto e service worker;
8. concluir o bootstrap pelo navegador;
9. validar convite, isolamento A/B e Push nos dispositivos disponíveis.

Não usar `down -v`, prune, remoção de volumes ou cadastro público como atalho.

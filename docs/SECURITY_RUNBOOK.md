# Security Runbook

## Rotação de `SECRET_KEY`

Trocar a chave invalida access tokens existentes. Para um incidente:

1. interrompa o tráfego externo;
2. revogue todas as sessões no servidor;
3. gere segredo forte fora do Git;
4. atualize o secret store/env do host;
5. reinicie backend, Worker e Beat;
6. confirme login novo, refresh, logout e `/ready`;
7. registre horário e motivo sem registrar a chave.

## Rotação da senha PostgreSQL

1. backup cifrado e verificado;
2. criar/alterar credencial no PostgreSQL;
3. atualizar secret store;
4. reiniciar os consumidores;
5. validar `/ready`, Worker, Beat e backup;
6. remover a credencial anterior.

Não publique 5432 para facilitar a operação.

## Revogação de sessões

- Logout comum revoga apenas a sessão atual.
- Troca de senha revoga todas as sessões do usuário.
- Em comprometimento, use a ferramenta administrativa para revogar todas as sessões sem apagar dados financeiros.
- Refresh tokens nunca devem ser exibidos, logados ou armazenados em plaintext.

## Recuperação administrativa de conta

A V1 não envia e-mail. A recuperação é deliberadamente administrativa e local ao host confiável:

1. confirmar identidade fora do VinanceOS;
2. executar o comando administrativo documentado no container backend, sem passar a nova senha como argumento visível no histórico;
3. informar a senha temporária por canal seguro;
4. revogar todas as sessões do usuário;
5. exigir troca após o primeiro login;
6. registrar somente operador, usuário, horário e resultado.

Nunca edite `hashed_password` manualmente no banco.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec backend \
  python -m backend.app.operations.admin_account reset-password --email usuario@example.com
```

O comando solicita a senha sem colocá-la nos argumentos ou no histórico do shell. Para apenas revogar credenciais:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml exec backend \
  python -m backend.app.operations.admin_account revoke-sessions --email usuario@example.com
```

## Conta comprometida

1. bloquear o acesso externo, preservando evidências;
2. revogar sessões do usuário afetado;
3. trocar senha e, se necessário, segredos globais;
4. revisar logs sanitizados por correlation ID;
5. verificar mudanças em household, ownership e decisões;
6. restaurar somente após determinar que houve corrupção de dados;
7. reabrir o acesso gradualmente.

## Backup comprometido

1. revogar/trocar passphrase e credenciais do armazenamento;
2. preservar checksums e audit trail;
3. produzir novo backup cifrado com segredo novo;
4. remover cópias antigas somente após retenção e validação jurídica/operacional;
5. testar restore do novo artefato em banco isolado.

## Desabilitar cadastro

Após bootstrap privado:

```text
REGISTRATION_ENABLED=false
VITE_REGISTRATION_ENABLED=false
```

Valide tanto a API quanto a ausência do CTA no frontend. Ocultar somente o botão não é controle de segurança.

## Logs e dados sensíveis

Nunca registrar:

- Authorization/Cookie;
- access/refresh token;
- senha ou segredo;
- payload financeiro completo;
- renda, dívida ou patrimônio completos.

Use IDs técnicos e correlation ID. Ao compartilhar logs para diagnóstico, revise a sanitização antes.

## Incidente de disco

- alerta: menos de 20% livre;
- crítico: menos de 10% livre;
- pare builds e tarefas não essenciais no crítico;
- não remova volumes;
- identifique images, build cache e logs separadamente;
- faça limpeza somente de cache reconstruível e com alvo conferido;
- valide PostgreSQL, Redis, Worker, Beat e backups após a recuperação.

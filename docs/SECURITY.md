# Security

Hardening aplicado:

- auth por access token e refresh token
- refresh token rotation
- tokens armazenados por hash
- logout revogando sessões/tokens
- bloqueio de usuário inativo
- rate limiting simples
- payload size limit
- CORS por ambiente
- secure headers
- request id
- logs sanitizados em audit logs
- DEBUG bloqueado em produção via settings

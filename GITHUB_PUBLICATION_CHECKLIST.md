# Vinance v2 — GitHub Publication Checklist

## Arquivos sensíveis

- [x] `.env` real não incluído.
- [x] Chave Groq real não incluída.
- [x] Senhas reais não incluídas.
- [x] Tokens JWT reais não incluídos.
- [x] Dumps de banco não incluídos.
- [x] Arquivos `.db`, `.sqlite`, `.dump` e `.bak` removidos/ignorados.

## Artefatos e caches

- [x] `frontend/node_modules/` não incluído.
- [x] `frontend/dist/` não incluído no pacote final.
- [x] `__pycache__/` não incluído.
- [x] `.pytest_cache/` não incluído.
- [x] `*.pyc` não incluído.
- [x] `tsconfig.tsbuildinfo` não incluído.
- [x] Logs locais não incluídos.

## Validação técnica

- [x] Backend compile validado com `python -m compileall backend/app scripts workers`.
- [x] Frontend install validado com `npm install`.
- [x] Frontend build validado com `npm run build`.
- [x] Build gerado removido antes do ZIP final.
- [x] `node_modules` removido antes do ZIP final.

## Documentação

- [x] README final atualizado.
- [x] DEPLOY_GUIDE.md criado.
- [x] GITHUB_PUBLICATION_CHECKLIST.md criado.
- [x] FASE_14_GITHUB_DEPLOY_PREP.md criado.
- [x] `.env.example` revisado.
- [x] `.gitignore` revisado.

## Status final

- [x] Projeto pronto para publicação profissional no GitHub.
- [x] Deploy futuro documentado.
- [x] Backend funcionalmente intocado na Fase 14.
- [x] Frontend visualmente intocado na Fase 14.

## Checklist adicional — correção Fase 14

- [x] Pasta `services/` legada arquivada em `_archived/fase14_legacy_services/services/`.
- [x] Referências legadas a Ollama removidas do caminho ativo do projeto.
- [x] Código legado com `OPENAI_API_KEY` removido do caminho ativo do projeto.
- [x] Ollama documentado como fora da arquitetura aprovada do Vinance v2.
- [x] `data/input/financas.xlsm` removido do pacote.
- [x] `data/imports/b3.xlsx` removido do pacote.
- [x] `data/input/.gitkeep` mantido.
- [x] `data/imports/.gitkeep` mantido.
- [x] `.gitignore` reforçado para bloquear planilhas locais `.xlsm` e `.xlsx`.

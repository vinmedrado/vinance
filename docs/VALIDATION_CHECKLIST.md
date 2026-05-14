# Checklist de Validação Pré-Testes

## Backend
- [x] `python -m compileall .`
- [x] testes unitários do advisor pré-teste
- [x] memória conversacional isolada por organização/usuário
- [x] RAG financeiro local
- [x] safety antes/depois da resposta
- [x] analytics sem prompt sensível

## Frontend
- [x] Advisor com layout premium
- [x] loading state
- [x] cards de contexto
- [x] feedback visual
- [x] empty state

## Teste manual recomendado
1. Abrir dashboard.
2. Abrir Advisor Financeiro.
3. Perguntar “quanto posso investir este mês?”.
4. Perguntar “vale quitar dívida ou investir?”.
5. Conferir se aparece disclaimer.
6. Testar sem Groq configurado para confirmar fallback local.
7. Testar com dados financeiros críticos e verificar bloqueio de recomendação agressiva.

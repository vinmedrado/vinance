# Hotfix — Mercado com fallback para asset_prices

## Objetivo
Corrigir a página Mercado para exibir dados reais já existentes em `asset_prices` quando as tabelas de fundamentos ainda estiverem vazias.

## Ajustes realizados
- `backend/app/market/service.py`
  - Adicionada leitura do último preço disponível por `market` em `asset_prices`.
- `backend/app/market/router.py`
  - Endpoints `/market/fundamentals/{classe}` agora tentam fundamentos primeiro.
  - Quando não há fundamentos, retornam fallback com `data_type = "price"`, `price/close`, `date`, `source`, `market` e metodologia `preço de mercado`.
- `backend/app/market/schemas.py`
  - Adicionado response flexível para preservar campos de fundamentos por classe e suportar fallback de preço.
- `frontend/src/pages/MarketPage.tsx`
  - Página Mercado agora identifica `data_type = "price"` e exibe tabela “Preços de mercado”.
  - Mantidas tabs FIIs/Ações/ETFs/BDRs/Cripto e identidade visual atual.
- `frontend/src/features/market/types/market.types.ts`
  - Tipagem atualizada para `data_type`, `price`, `close`, `date`, `label` e `methodology`.

## Não alterado
- Providers
- Celery
- ML
- Advisor
- Financial
- Migrations
- Auth
- Regras de negócio

## Validação executada
- `python -m compileall backend/app scripts workers`: OK
- `npm install`: OK
- `npm run build`: OK

# Product Overview — FinanceOS

FinanceOS foi reposicionado como ERP financeiro inteligente premium. A proposta principal não é ser apenas dashboard de investimentos, mas conectar controle financeiro diário com orçamento, metas, carteira, alertas e inteligência.

## Fluxo do usuário

1. Login no frontend React.
2. Onboarding financeiro.
3. Cadastro de receitas, despesas, contas e cartões.
4. Escolha do modelo de orçamento.
5. Diagnóstico financeiro.
6. Sugestão de valor mensal para investir.
7. Acompanhamento de carteira, alertas e oportunidades.

## Diferenciais

- Despesas e receitas alimentam orçamento.
- Orçamento calcula limite e meta de investimento.
- Diagnóstico gera score, previsão e recomendações.
- ML, backtest e ranking seguem preservados como camada de inteligência.

---

## Ultra Premium UX Patch

O frontend oficial do FinanceOS é React/Vite com TypeScript. Este patch adicionou uma camada de design system premium, componentes reutilizáveis, dark mode refinado, responsividade, lazy loading e melhorias visuais nas telas principais do ERP financeiro.

Telas refinadas:
- Login
- Onboarding
- Dashboard Financeiro
- Despesas
- Orçamento
- Metas/CRUDs financeiros
- Diagnóstico Financeiro
- Investimentos/Carteira/Alertas
- Planos
- Landing page

Comandos principais:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Backend:

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker compose up --build
```

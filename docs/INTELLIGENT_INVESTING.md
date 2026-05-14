# Vinance Intelligent Investing

O módulo de inteligência financeira transforma dados do ERP em orientação simples para o usuário final. Ele não tenta prever qual ativo vai subir amanhã e não transforma o Vinance em terminal de trading.

## Fluxo

1. Perfil financeiro: renda, despesas, reserva, meta, prazo, experiência e tolerância a risco.
2. Capacidade financeira: calcula sobra mensal, margem segura e aporte saudável.
3. Alocação inteligente: sugere percentuais por classe de mercado.
4. Backtest personalizado: simula cenários com aporte mensal, prazo e risco.
5. Scoring contextual: ranqueia ativos por qualidade/aderência ao perfil.
6. Recomendação final: traduz tudo em linguagem simples.

## Disclaimer

O Vinance fornece simulações e análises educacionais baseadas em dados históricos e modelos estatísticos. Isso não constitui recomendação financeira.


## Fluxo financeiro principal

O Vinance agora calcula automaticamente o modelo financeiro ideal antes de sugerir investimentos. O fluxo oficial é: renda cadastrada, despesas e dívidas, diagnóstico financeiro, recomendação do modelo mensal, plano de ação e somente depois investimentos com ML/backtest.

A tela **Meu Plano Financeiro** usa o `BudgetModelAdvisorService` para escolher entre Recuperação Financeira, Base Zero, 70/20/10, 60/30/10, 50/30/20 ou Personalizado. As recomendações são educativas e não constituem recomendação financeira.

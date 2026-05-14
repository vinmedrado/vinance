# Backtest Personalizado

O backtest do Vinance é um simulador de planejamento, não uma ferramenta de day trade.

Ele considera:

- capacidade mensal de aporte;
- perfil de risco;
- horizonte até a meta;
- estratégia sugerida;
- benchmarks simulados como CDI, IPCA e Ibovespa;
- cenários pessimista, base e otimista.

Saída principal para o usuário:

- valor histórico simulado;
- pior queda simulada;
- chance estimada de atingir a meta;
- risco baixo, médio ou alto;
- comparação com benchmarks.

As métricas técnicas ficam encapsuladas no backend e não são o foco da experiência.

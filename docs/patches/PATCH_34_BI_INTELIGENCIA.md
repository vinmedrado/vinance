# FinanceOS — PATCH 34

BI da Inteligência — Visualização Histórica, Tendências e Evolução

Incluído:
- `services/intelligence_bi_service.py`
- `pages/15_BI_Inteligencia.py`
- KPIs:
  - último score global
  - delta vs execução anterior
  - tendência atual
  - melhor score histórico
  - pior score histórico
  - média dos últimos 5 scores
  - quantidade de execuções inteligentes
- Gráficos:
  - evolução do score global
  - delta entre execuções
  - distribuição de tendências
  - alertas ao longo do tempo
  - oportunidades ao longo do tempo
  - score vs média móvel
- Filtros:
  - período
  - trend
  - score mínimo
  - score máximo
- tabela analítica em expander
- leitura executiva determinística
- integração com Home

Não alterado:
- backtest
- multi_factor.py
- strategy_runner.py
- jobs/fila
- orquestrador
- lógica de estratégia

Execução:
streamlit run legacy_streamlit/app.py

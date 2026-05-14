# FinanceOS — PATCH 38

Camada Investidor + Oportunidades por Mercado

Incluído:
- `services/investor_service.py`
- `pages/18_Investidor_Dashboard.py`
- `pages/19_Oportunidades_Mercado.py`
- toggle simples Modo Investidor/Admin no sidebar do app principal

Camada Investidor:
- não expõe ML técnico
- não expõe datasets
- não expõe modelos
- não expõe logs
- mostra oportunidades por mercado:
  - Ações
  - FIIs
  - ETFs
  - BDRs
  - Cripto

Cálculo inicial:
- score_final = média ponderada de:
  - ML score normalizado
  - confiança
  - qualidade dos dados
- classificação:
  - Forte
  - Boa
  - Neutra
  - Evitar
- risco:
  - Baixo
  - Médio
  - Alto
- explicação simples via build_simple_explanation(asset)

Não implementado:
- contas reais
- integração com corretora
- execução de ordem
- ML + backtest combinado
- carteira automatizada

Execução:
streamlit run legacy_streamlit/app.py

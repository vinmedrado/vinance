# FinanceOS — PATCH 32

Inteligência Avançada dos Agentes

Incluído/Atualizado:
- Pipeline coordenado de agentes (catalog → strategy → risk → analyst → explainer)
- Score global do sistema (0–100 + label)
- Consolidação de insights por prioridade (high/medium/low)
- Padronização completa de output dos agentes
- Explicação final mais inteligente (agent_explainer)
- Integração com orquestrador com campos:
  - global_intelligence_score
  - top_insights
  - warnings
  - opportunities
  - final_explanation
- Nova UI avançada na página 14

Características:
- Funciona 100% sem IA externa (fallback determinístico)
- Suporte opcional a OpenAI-compatible API
- Não altera estratégia, apenas interpreta

Execução:
streamlit run legacy_streamlit/app.py

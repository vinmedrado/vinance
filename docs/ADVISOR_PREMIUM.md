# Advisor Premium Vinance

O Advisor Premium transforma a resposta do copiloto em uma leitura consultiva, sem virar terminal técnico. Ele usa diagnóstico curto, leitura de contexto, decisão recomendada, riscos, próximos passos e alternativas conservadora/equilibrada/agressiva quando fizer sentido.

## Princípios
- Usar dados reais do ERP antes de responder.
- Priorizar organização financeira quando saúde financeira está crítica.
- Evitar promessa de retorno, ordem de compra/venda e linguagem agressiva.
- Explicar o próximo passo de forma prática.

## Saída principal
- `answer`: resposta humanizada.
- `premium_advisor.diagnosis`: fase e score.
- `premium_advisor.recommended_decision`: ação principal.
- `premium_advisor.alternatives`: opções por perfil de risco.
- `disclaimer`: aviso educacional obrigatório.

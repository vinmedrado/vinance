# Budget Model Advisor

O Budget Model Advisor é o motor principal do fluxo financeiro do Vinance: **renda → despesas/dívidas → modelo ideal → plano mensal → capacidade de investir**.

## Modelos suportados

- **Recuperação financeira**: priorizado quando há contas atrasadas.
- **Base Zero**: indicado quando a renda está muito comprometida.
- **70/20/10**: usado para controle e eliminação gradual de contas.
- **60/30/10**: usado para reorganização financeira.
- **50/30/20**: usado para equilíbrio entre vida, reserva e investimento.
- **Personalizado para metas e investimentos**: usado quando as despesas estão abaixo de 50% da renda.

## Regras principais

- Despesas + dívidas >= 85% da renda: Base Zero ou 70/20/10.
- Despesas entre 70% e 85%: 60/30/10.
- Despesas entre 50% e 70%: 50/30/20.
- Despesas abaixo de 50%: personalizado para metas/investimentos.
- Contas atrasadas: recuperação financeira tem prioridade.

## Saída

A engine retorna:

- modelo recomendado;
- confiança;
- motivo humano;
- plano de ação;
- limites sugeridos;
- alertas;
- capacidade segura de investimento;
- gate de investimentos.

## Disclaimer

O Vinance fornece simulações e análises educacionais. Isso não constitui recomendação financeira.

import requests


def analisar_financas(contexto: str):
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3.2:3b",
        "prompt": contexto,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "IA não retornou resposta.")
    except Exception as e:
        return f"Erro ao consultar Ollama: {e}"

def montar_contexto(df, planejamento, saldo):
    total = df["valor_total"].sum()
    total_pagar = df["valor_a_pagar"].sum()
    
    cobertura = saldo - total_pagar
    percentual_comprometido = (total_pagar / saldo * 100) if saldo > 0 else 0

    return f"""
Você é um mentor financeiro.

Sua função NÃO é analisar ou decidir.
As decisões já foram tomadas pelo sistema.

Sua função é apenas EXPLICAR de forma clara e profissional.

DADOS:

Saldo: R$ {saldo:.2f}
Total a pagar: R$ {total_pagar:.2f}
Cobertura: R$ {cobertura:.2f}
Comprometimento: {percentual_comprometido:.2f}%

Método definido: {planejamento['metodo']['metodo']}

Resumo de prioridade:
Alta: R$ {planejamento['resumo_prioridade']['Alta']:.2f}
Média: R$ {planejamento['resumo_prioridade']['Média']:.2f}
Baixa: R$ {planejamento['resumo_prioridade']['Baixa']:.2f}

REGRAS DEFINIDAS PELO SISTEMA:
- Não há urgência se Alta = 0
- Situação saudável se comprometimento < 30%
- Contas de prioridade baixa devem apenas ser programadas

EXPLIQUE ao usuário:
- situação atual
- se há urgência ou não
- o que fazer de forma simples

Não questione os dados.
Não gere novas análises.
Não invente problemas.
Evite repetir a mesma informação de formas diferentes.
Seja objetivo em no máximo 5 linhas.
Não confunda despesas com investimento ou reserva.
Não mencione impostos ou renda se não estiverem nos dados.
Não explique conceitos financeiros, apenas aplique.
Seja extremamente direto, com no máximo 4 frases.
Use linguagem simples e natural, como um app profissional.
"""
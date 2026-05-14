from dataclasses import dataclass


@dataclass
class PerfilInvestidor:
    nome: str
    pontuacao: int
    distribuicao: dict


PERFIS = {
    "Conservador": {
        "Ações": 0.05,
        "BDRs": 0.05,
        "ETFs": 0.05,
        "FIIs": 0.15,
        "Renda Fixa": 0.60,
        "Reserva de Emergência": 0.10,
        "Criptomoedas": 0.00,
    },
    "Moderado": {
        "Ações": 0.15,
        "BDRs": 0.05,
        "ETFs": 0.15,
        "FIIs": 0.20,
        "Renda Fixa": 0.35,
        "Reserva de Emergência": 0.05,
        "Criptomoedas": 0.05,
    },
    "Arrojado": {
        "Ações": 0.20,
        "BDRs": 0.10,
        "ETFs": 0.20,
        "FIIs": 0.20,
        "Renda Fixa": 0.15,
        "Reserva de Emergência": 0.05,
        "Criptomoedas": 0.10,
    },
}


def calcular_nome_perfil(pontuacao: int) -> str:
    if pontuacao <= 6:
        return "Conservador"
    if pontuacao <= 10:
        return "Moderado"
    return "Arrojado"


def calcular_perfil(respostas: list[int]) -> PerfilInvestidor:
    pontuacao = sum(respostas)
    nome = calcular_nome_perfil(pontuacao)
    distribuicao = PERFIS[nome]

    return PerfilInvestidor(
        nome=nome,
        pontuacao=pontuacao,
        distribuicao=distribuicao,
    )


def calcular_alocacao(aporte: float, distribuicao: dict) -> list[dict]:
    alocacao = []

    for classe, percentual in distribuicao.items():
        valor = round(aporte * percentual, 2)

        alocacao.append({
            "classe": classe,
            "percentual": percentual,
            "valor": valor,
        })

    return alocacao
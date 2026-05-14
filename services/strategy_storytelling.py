from __future__ import annotations

from typing import Any, Dict

from services.benchmark_service import calculate_alpha


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def generate_story(metrics: Dict[str, Any], benchmark: Dict[str, Any]) -> str:
    """Storytelling determinístico para explicar resultado sem IA."""
    total_return = _num(metrics.get("total_return"))
    drawdown = _num(metrics.get("max_drawdown"))
    sharpe = _num(metrics.get("sharpe_ratio"))
    turnover = _num(metrics.get("turnover"))
    ibov_return = _num(benchmark.get("ibov_return"))
    cdi_return = _num(benchmark.get("cdi_return"))
    alpha_ibov = calculate_alpha(total_return, ibov_return)
    alpha_cdi = calculate_alpha(total_return, cdi_return)

    parts = []
    if alpha_ibov > 0:
        parts.append("Essa estratégia superou o mercado no período analisado.")
    elif alpha_ibov < 0:
        parts.append("A estratégia teve desempenho inferior ao IBOV no período.")
    else:
        parts.append("A estratégia ficou próxima do desempenho do IBOV no período.")

    if alpha_cdi > 0:
        parts.append("Também entregou prêmio sobre o CDI estimado.")
    elif total_return > 0:
        parts.append("Apesar do retorno positivo, ficou abaixo do CDI estimado.")

    if drawdown <= -0.30:
        parts.append("Apresentou volatilidade elevada, com quedas relevantes.")
    elif drawdown > -0.20:
        parts.append("O drawdown ficou em uma faixa mais controlada.")

    if sharpe > 0.30:
        parts.append("Mostrou boa relação risco-retorno.")
    elif sharpe <= 0:
        parts.append("A relação risco-retorno foi fraca no período.")

    if turnover > 30:
        parts.append("O nível de operações foi elevado, podendo impactar custos e estabilidade.")
    elif turnover < 10:
        parts.append("A rotação da carteira ficou relativamente controlada.")

    return " ".join(parts)

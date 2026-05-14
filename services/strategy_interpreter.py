from __future__ import annotations

from typing import Any, Dict, List


def _num(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = metrics.get(key, default)
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def calculate_strategy_score(metrics: Dict[str, Any]) -> int:
    """Calcula score visual 0-100 para uso na UI. Não persiste nada no banco."""
    total_return = _num(metrics, "total_return")
    max_drawdown = _num(metrics, "max_drawdown")
    sharpe_ratio = _num(metrics, "sharpe_ratio")
    turnover = _num(metrics, "turnover")
    win_rate = _num(metrics, "win_rate")

    score = 0.0

    # Retorno: até 30 pontos
    if total_return > 0:
        score += min(30.0, total_return / 0.30 * 30.0)

    # Drawdown: até 25 pontos; quanto menos negativo, melhor.
    if max_drawdown >= -0.10:
        score += 25.0
    elif max_drawdown >= -0.20:
        score += 20.0
    elif max_drawdown >= -0.30:
        score += 14.0
    elif max_drawdown >= -0.40:
        score += 7.0
    else:
        score += 0.0

    # Sharpe: até 20 pontos
    if sharpe_ratio > 0:
        score += min(20.0, sharpe_ratio / 1.0 * 20.0)

    # Turnover: até 15 pontos; quanto menor, melhor.
    if turnover <= 5:
        score += 15.0
    elif turnover <= 10:
        score += 12.0
    elif turnover <= 15:
        score += 8.0
    elif turnover <= 25:
        score += 4.0

    # Win rate: até 10 pontos
    if win_rate > 0:
        score += min(10.0, win_rate / 0.60 * 10.0)

    return int(max(0, min(100, round(score))))


def classify_strategy(metrics: Dict[str, Any]) -> Dict[str, Any]:
    total_return = _num(metrics, "total_return")
    max_drawdown = _num(metrics, "max_drawdown")
    sharpe_ratio = _num(metrics, "sharpe_ratio")
    turnover = _num(metrics, "turnover")
    score = calculate_strategy_score(metrics)

    if total_return < 0 and max_drawdown <= -0.40 and turnover > 30:
        label = "Inviável"
        level = "error"
    elif total_return <= 0 or sharpe_ratio <= 0:
        label = "Fraca"
        level = "error"
    elif total_return > 0.25 and max_drawdown > -0.25 and sharpe_ratio > 0.5 and turnover < 10:
        label = "Excelente"
        level = "success"
    elif total_return > 0.10 and max_drawdown > -0.30 and sharpe_ratio > 0.25 and turnover < 15:
        label = "Boa"
        level = "success"
    elif total_return > 0.10 and max_drawdown <= -0.30:
        label = "Promissora, mas arriscada"
        level = "warning"
    elif total_return > 0 and max_drawdown > -0.20 and turnover < 5:
        label = "Conservadora"
        level = "info"
    else:
        label = "Promissora, mas arriscada" if total_return > 0 else "Fraca"
        level = "warning" if total_return > 0 else "error"

    return {"label": label, "level": level, "score": score}


def generate_recommendations(metrics: Dict[str, Any]) -> List[str]:
    total_return = _num(metrics, "total_return")
    max_drawdown = _num(metrics, "max_drawdown")
    sharpe_ratio = _num(metrics, "sharpe_ratio")
    win_rate = _num(metrics, "win_rate")
    total_trades = _num(metrics, "total_trades")
    turnover = _num(metrics, "turnover")

    recommendations: List[str] = []

    if turnover > 20:
        recommendations.append(
            "Turnover muito alto. Considere aumentar rebalance_threshold_pct, reduzir top_n ou aumentar min_holding_period_rebalances."
        )
    if max_drawdown <= -0.35:
        recommendations.append(
            "Drawdown elevado. Considere aumentar weight_risk, reduzir max_position_pct ou aumentar cash_buffer_pct."
        )
    if total_return <= 0:
        recommendations.append(
            "Retorno fraco no período. Teste outro perfil ou ajuste os pesos da estratégia."
        )
    if sharpe_ratio < 0.2:
        recommendations.append(
            "Sharpe baixo. A estratégia não está compensando bem o risco assumido."
        )
    if win_rate and win_rate < 0.45:
        recommendations.append(
            "Win rate baixo. Avalie filtros de entrada ou maior peso em tendência."
        )
    if total_trades > 200:
        recommendations.append(
            "Número de trades elevado. A estratégia pode estar operando demais."
        )

    if not recommendations:
        recommendations.append(
            "Estratégia consistente no período testado. Ainda assim, valide em outros períodos antes de usar."
        )

    return recommendations


def summarize_strategy(metrics: Dict[str, Any]) -> str:
    total_return = _num(metrics, "total_return")
    max_drawdown = _num(metrics, "max_drawdown")
    sharpe_ratio = _num(metrics, "sharpe_ratio")
    turnover = _num(metrics, "turnover")

    if total_return > 0 and max_drawdown > -0.20 and turnover < 5:
        return (
            "Essa estratégia teve retorno positivo, baixo drawdown e turnover controlado. "
            "É uma configuração mais conservadora e estável no período testado."
        )
    if total_return > 0 and max_drawdown <= -0.30:
        return (
            "Essa estratégia apresentou retorno positivo, mas com drawdown elevado. "
            "Ela pode ser promissora, porém precisa de maior controle de risco."
        )
    if total_return > 0 and turnover > 20:
        return (
            "Essa estratégia gerou retorno positivo, mas com rotação muito alta. "
            "O custo operacional e a troca excessiva de ativos podem prejudicar o resultado real."
        )
    if total_return > 0 and sharpe_ratio > 0:
        return (
            "Essa estratégia apresentou retorno positivo e alguma compensação pelo risco assumido. "
            "Vale comparar com outros períodos e perfis antes de considerar uso operacional."
        )
    return (
        "Essa estratégia teve desempenho fraco no período testado. "
        "Considere ajustar pesos, perfil, universo de ativos ou período de simulação."
    )

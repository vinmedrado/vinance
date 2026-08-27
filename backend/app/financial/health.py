from __future__ import annotations


def classify_financial_health(
    commitment: float | None,
    reserve_months: float,
    balance: float,
    income: float,
) -> tuple[str, str]:
    """Classify the legacy executive profile without database dependencies."""
    balance_ratio = balance / income if income > 0 else 0
    if income <= 0:
        return "arriscado", "Cadastre sua renda mensal para o FinanceOS calcular sua saúde financeira real."
    if balance < 0 or (commitment is not None and commitment > 0.75):
        return "arriscado", "Seu orçamento está pressionado: despesas consomem grande parte da renda e reduzem sua margem de segurança."
    if reserve_months >= 6 and balance_ratio >= 0.20 and (commitment is None or commitment <= 0.60):
        return "seguro", "Sua base financeira está saudável: existe sobra mensal e reserva próxima do nível recomendado."
    if reserve_months >= 3 and balance_ratio > 0:
        return "moderado", "Você tem alguma margem, mas ainda precisa fortalecer reserva e controlar novas parcelas."
    return "arriscado", "A principal fragilidade está na baixa reserva de emergência e/ou pouca sobra mensal."

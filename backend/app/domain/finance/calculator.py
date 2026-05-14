from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Literal

getcontext().prec = 34

DISCLAIMER = (
    "Simulação financeira para decisão e comparação. Não substitui proposta bancária oficial. "
    "Taxas, IOF, seguros, tarifas, aprovação, atualização monetária e regras finais variam por instituição."
)

System = Literal["SAC", "PRICE"]
AssetType = Literal["car", "motorcycle", "real_estate"]
IOFScenario = Literal["pf_auto", "pf_real_estate_exempt", "custom", "none"]

CENT = Decimal("0.01")
ZERO = Decimal("0")
ONE = Decimal("1")
IOF_DAILY_RATE_PF = Decimal("0.000082")
IOF_ADDITIONAL_RATE_PF = Decimal("0.0038")
IOF_MAX_DAYS_PF = Decimal("365")
VALIDATION_TOLERANCE = Decimal("0.00")


@dataclass(frozen=True)
class FinancingInput:
    asset_type: AssetType | str
    system: System
    asset_value: float
    down_payment: float
    months: int
    monthly_rate: float
    monthly_income: float | None = None
    max_income_commitment_pct: float = 0.30
    iof_scenario: IOFScenario = "pf_auto"
    iof_rate: float | None = None
    admin_fee: float = 0.0
    operational_fee: float = 0.0
    appraisal_fee: float = 0.0
    registry_fee: float = 0.0
    insurance_monthly: float = 0.0
    mip_monthly: float = 0.0
    dfi_monthly: float = 0.0
    include_optional_insurance: bool = True


def D(value: float | int | str | Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def money(value: Decimal | float | int | str) -> Decimal:
    return D(value).quantize(CENT, rounding=ROUND_HALF_EVEN)


def to_float(value: Decimal | float | int | str) -> float:
    return float(money(value))


def rate_float(value: Decimal | float | int | str) -> float:
    return float(D(value))


def annual_effective_rate(monthly_rate: float | Decimal) -> float:
    r = D(monthly_rate)
    return float((ONE + r) ** 12 - ONE)


def price_payment(principal: float | Decimal, monthly_rate: float | Decimal, months: int) -> float:
    p = D(principal)
    r = D(monthly_rate)
    if months <= 0:
        return 0.0
    n = D(months)
    if r == ZERO:
        return float(p / n)
    factor = (ONE + r) ** months
    return float(p * (r * factor) / (factor - ONE))


def calculate_iof(financed_amount: Decimal, months: int, scenario: IOFScenario = "pf_auto", explicit_rate: float | None = None) -> Decimal:
    if scenario == "none" or scenario == "pf_real_estate_exempt":
        return ZERO
    if scenario == "custom" or explicit_rate is not None:
        if explicit_rate is None:
            raise ValueError("iof_rate é obrigatório quando iof_scenario='custom'")
        return money(financed_amount * D(explicit_rate))
    days = min(D(months) * Decimal("30"), IOF_MAX_DAYS_PF)
    return money(financed_amount * (IOF_ADDITIONAL_RATE_PF + IOF_DAILY_RATE_PF * days))


def _irr_monthly(cashflows: list[Decimal]) -> Decimal:
    """Calcula CET mensal por bisseção com float interno controlado.

    Os valores monetários já entram arredondados em Decimal. A busca da taxa usa
    float apenas para performance numérica em cenários longos como 420 meses.
    """
    cfs = [float(cf) for cf in cashflows]
    low = -0.999999
    high = 1.0

    def npv(rate: float) -> float:
        factor = 1.0 / (1.0 + rate)
        discount = 1.0
        total = 0.0
        for cf in cfs:
            total += cf * discount
            discount *= factor
        return total

    # Para fluxo convencional (+entrada do banco ao cliente, -parcelas),
    # NPV é decrescente conforme a taxa sobe. Amplia o limite superior se necessário.
    while npv(high) > 0 and high < 100.0:
        high *= 2.0

    for _ in range(100):
        mid = (low + high) / 2.0
        val = npv(mid)
        if abs(val) < 1e-7:
            return D(mid)
        if val > 0:
            low = mid
        else:
            high = mid
    return D((low + high) / 2.0)

def _risk_score(commitment: Decimal | None, ltv: Decimal, months: int, monthly_rate: Decimal) -> tuple[str, int]:
    score = 0
    score += 20 if ltv <= Decimal("0.70") else 38 if ltv <= Decimal("0.85") else 58
    score += 8 if months <= 48 else 18 if months <= 120 else 32
    score += 8 if monthly_rate <= Decimal("0.012") else 18 if monthly_rate <= Decimal("0.02") else 32
    if commitment is not None:
        score += 8 if commitment <= Decimal("0.25") else 25 if commitment <= Decimal("0.35") else 45
    score = min(score, 100)
    return ("baixo" if score <= 45 else "medio" if score <= 70 else "alto", score)


def _validate_input(data: FinancingInput) -> None:
    if data.months <= 0:
        raise ValueError("Prazo deve ser maior que zero")
    if data.months > 420:
        raise ValueError("Prazo acima do limite operacional suportado")
    if D(data.asset_value) <= ZERO:
        raise ValueError("Valor do bem deve ser maior que zero")
    if D(data.down_payment) < ZERO:
        raise ValueError("Entrada não pode ser negativa")
    if D(data.down_payment) >= D(data.asset_value):
        raise ValueError("A entrada deve ser menor que o valor do bem")
    if D(data.monthly_rate) < ZERO:
        raise ValueError("Taxa mensal não pode ser negativa")
    if data.system not in {"SAC", "PRICE"}:
        raise ValueError("Sistema deve ser SAC ou PRICE")


def _validate_math(result: dict) -> dict[str, float | bool]:
    schedule = result["schedule"]
    principal = money(result["principal_with_costs"])
    total_installments = money(result["total_installments"])
    total_cost = money(result["total_cost"])
    down_payment = money(result["down_payment"])
    final_balance = money(schedule[-1]["balance"] if schedule else ZERO)
    principal_repaid = money(sum(D(row["amortization"]) for row in schedule))
    schedule_sum = money(sum(D(row["payment"]) for row in schedule))
    expected_total_cost = money(down_payment + total_installments)

    validations = {
        "final_balance_zero": final_balance == ZERO,
        "sum_installments_matches_schedule": schedule_sum == total_installments,
        "total_cost_matches_down_plus_installments": expected_total_cost == total_cost,
        "principal_repaid_matches_principal": principal_repaid == principal,
        "zero_tolerance_enabled": VALIDATION_TOLERANCE == ZERO,
        "sum_installments": to_float(schedule_sum),
        "stored_total_installments": to_float(total_installments),
        "down_payment_plus_installments": to_float(expected_total_cost),
        "stored_total_cost": to_float(total_cost),
        "principal_repaid": to_float(principal_repaid),
        "principal_with_costs": to_float(principal),
        "final_balance": to_float(final_balance),
    }
    failed = [
        key for key in (
            "final_balance_zero",
            "sum_installments_matches_schedule",
            "total_cost_matches_down_plus_installments",
            "principal_repaid_matches_principal",
            "zero_tolerance_enabled",
        )
        if validations[key] is False
    ]
    if failed:
        raise ValueError(f"Divergência matemática na simulação: {', '.join(failed)}")
    return validations

def calculate_schedule(data: FinancingInput) -> dict:
    _validate_input(data)

    asset_value = money(data.asset_value)
    down_payment = money(data.down_payment)
    monthly_rate = D(data.monthly_rate)
    financed_amount = money(asset_value - down_payment)

    iof_amount = calculate_iof(financed_amount, data.months, data.iof_scenario, data.iof_rate)
    admin_fee = money(data.admin_fee)
    operational_fee = money(data.operational_fee)
    appraisal_fee = money(data.appraisal_fee)
    registry_fee = money(data.registry_fee)
    credit_one_time_costs = money(iof_amount + admin_fee + operational_fee + appraisal_fee + registry_fee)
    principal = money(financed_amount + credit_one_time_costs)

    optional_insurance = money(D(data.insurance_monthly) if data.include_optional_insurance else ZERO)
    mip = money(data.mip_monthly)
    dfi = money(data.dfi_monthly)
    monthly_external_costs = money(optional_insurance + mip + dfi)

    schedule: list[dict] = []
    balance = principal
    fixed_amort = principal / D(data.months)
    fixed_price = D(price_payment(principal, monthly_rate, data.months))
    accumulated_interest = ZERO
    accumulated_amortization = ZERO

    for month in range(1, data.months + 1):
        opening_balance = balance
        interest = money(opening_balance * monthly_rate)
        if data.system == "SAC":
            amortization = money(min(fixed_amort, opening_balance))
            if month == data.months:
                amortization = opening_balance
            base_payment = money(amortization + interest)
        else:
            base_payment = money(fixed_price)
            amortization = money(min(base_payment - interest, opening_balance))
            if month == data.months:
                amortization = opening_balance
                base_payment = money(amortization + interest)

        balance = money(max(ZERO, opening_balance - amortization))
        payment = money(base_payment + monthly_external_costs)
        accumulated_interest = money(accumulated_interest + interest)
        accumulated_amortization = money(accumulated_amortization + amortization)
        schedule.append({
            "month": month,
            "opening_balance": to_float(opening_balance),
            "payment": to_float(payment),
            "base_payment": to_float(base_payment),
            "amortization": to_float(amortization),
            "interest": to_float(interest),
            "insurance": to_float(optional_insurance),
            "mip": to_float(mip),
            "dfi": to_float(dfi),
            "monthly_costs": to_float(monthly_external_costs),
            "accumulated_interest": to_float(accumulated_interest),
            "accumulated_amortization": to_float(accumulated_amortization),
            "balance": to_float(balance),
        })

    total_payments = money(sum(D(row["payment"]) for row in schedule))
    total_base_payments = money(sum(D(row["base_payment"]) for row in schedule))
    total_interest = money(sum(D(row["interest"]) for row in schedule))
    optional_insurance_total = money(optional_insurance * D(data.months))
    mip_total = money(mip * D(data.months))
    dfi_total = money(dfi * D(data.months))
    insurance_total = money(optional_insurance_total + mip_total + dfi_total)
    first_payment = D(schedule[0]["payment"])
    last_payment = D(schedule[-1]["payment"])
    average_payment = money(total_payments / D(data.months))

    cashflows = [financed_amount] + [-D(row["payment"]) for row in schedule]
    cet_monthly = _irr_monthly(cashflows)
    cet_annual = (ONE + cet_monthly) ** 12 - ONE

    monthly_income = D(data.monthly_income) if data.monthly_income else None
    income_commitment = (first_payment / monthly_income) if monthly_income and monthly_income > ZERO else None
    ltv = financed_amount / asset_value
    risk_label, risk_score = _risk_score(income_commitment, ltv, data.months, monthly_rate)
    approved = None
    reason = None
    if income_commitment is not None:
        max_commitment = D(data.max_income_commitment_pct)
        approved = income_commitment <= max_commitment and risk_score < 80
        reason = "Aprovável pelos parâmetros informados" if approved else "Reprovável: comprometimento, prazo, entrada ou risco acima do limite"


    calculation_audit = [
        f"Entrada validada: system={data.system}, months={data.months}, asset_type={data.asset_type}",
        f"Valor do bem={asset_value}; entrada={down_payment}; principal financiado base={financed_amount}",
        f"IOF={iof_amount}; custos à vista no crédito={credit_one_time_costs}; principal com custos={principal}",
        "Arredondamento financeiro: Decimal + ROUND_HALF_EVEN em todos os valores monetários",
        f"Seguro opcional mensal={optional_insurance}; MIP mensal={mip}; DFI mensal={dfi}; custos mensais={monthly_external_costs}",
    ]

    result = {
        "asset_type": data.asset_type,
        "system": data.system,
        "asset_value": to_float(asset_value),
        "down_payment": to_float(down_payment),
        "financed_amount": to_float(financed_amount),
        "principal_with_costs": to_float(principal),
        "months": data.months,
        "monthly_rate": rate_float(monthly_rate),
        "annual_effective_rate": annual_effective_rate(monthly_rate),
        "estimated_cet_monthly": rate_float(cet_monthly),
        "estimated_cet_annual": rate_float(cet_annual),
        "iof_scenario": data.iof_scenario,
        "iof_amount": to_float(iof_amount),
        "credit_one_time_costs": to_float(credit_one_time_costs),
        "cet_components": {
            "interest_total": to_float(total_interest),
            "iof_amount": to_float(iof_amount),
            "admin_fee": to_float(admin_fee),
            "operational_fee": to_float(operational_fee),
            "appraisal_fee": to_float(appraisal_fee),
            "registry_fee": to_float(registry_fee),
            "optional_insurance_total": to_float(optional_insurance_total),
            "insurance_total": to_float(insurance_total),
            "mip_total": to_float(mip_total),
            "dfi_total": to_float(dfi_total),
        },
        "admin_fee": to_float(admin_fee),
        "operational_fee": to_float(operational_fee),
        "appraisal_fee": to_float(appraisal_fee),
        "registry_fee": to_float(registry_fee),
        "insurance_total": to_float(insurance_total),
        "total_installments": to_float(total_payments),
        "total_cost": to_float(down_payment + total_payments),
        "total_financed_cost": to_float(total_base_payments + insurance_total),
        "total_interest": to_float(total_interest),
        "first_payment": to_float(first_payment),
        "last_payment": to_float(last_payment),
        "average_payment": to_float(average_payment),
        "income_commitment_pct": round(float(income_commitment), 6) if income_commitment is not None else None,
        "ltv_pct": round(float(ltv), 6),
        "risk_level": risk_label,
        "risk_score": risk_score,
        "approved": approved,
        "approval_reason": reason,
        "schedule": schedule,
        "input_snapshot": asdict(data),
        "calculation_audit": calculation_audit,
        "disclaimer": DISCLAIMER,
    }
    result["math_validation"] = _validate_math(result)
    result["calculation_audit"].append(f"Validação matemática zero tolerância aprovada: {result['math_validation']}")

    extra_down = money(min(asset_value * Decimal("0.10"), financed_amount * Decimal("0.30")))
    reduced_interest = calculate_interest_only(data, extra_down_payment=float(extra_down))
    result["comparison_save_more_down_payment"] = {
        "extra_down_payment": to_float(extra_down),
        "estimated_interest_saving": to_float(max(ZERO, total_interest - D(reduced_interest))),
    }
    return result


def calculate_interest_only(data: FinancingInput, extra_down_payment: float) -> float:
    reduced_down = min(D(data.asset_value) - ONE, D(data.down_payment) + D(extra_down_payment))
    reduced = FinancingInput(**{**asdict(data), "down_payment": float(reduced_down)})
    result = calculate_schedule_without_strategy(reduced)
    return float(D(result["total_interest"]))


def calculate_schedule_without_strategy(data: FinancingInput) -> dict:
    _validate_input(data)
    asset_value = money(data.asset_value)
    down_payment = money(data.down_payment)
    monthly_rate = D(data.monthly_rate)
    financed_amount = money(asset_value - down_payment)
    principal = money(
        financed_amount
        + calculate_iof(financed_amount, data.months, data.iof_scenario, data.iof_rate)
        + D(data.admin_fee)
        + D(data.operational_fee)
        + D(data.appraisal_fee)
        + D(data.registry_fee)
    )
    balance = principal
    fixed_amort = principal / D(data.months)
    fixed_price = D(price_payment(principal, monthly_rate, data.months))
    total_interest = ZERO
    for month in range(1, data.months + 1):
        interest = money(balance * monthly_rate)
        if data.system == "SAC":
            amortization = money(min(fixed_amort, balance))
            if month == data.months:
                amortization = balance
        else:
            base_payment = money(fixed_price)
            amortization = money(min(base_payment - interest, balance))
            if month == data.months:
                amortization = balance
        total_interest = money(total_interest + interest)
        balance = money(max(ZERO, balance - amortization))
    return {"total_interest": to_float(total_interest)}

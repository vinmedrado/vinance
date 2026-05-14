import pytest

from app.financing.services.calculator import FinancingInput, calculate_iof, calculate_schedule, price_payment


def test_price_fixed_payment_is_constant_without_external_costs():
    data = FinancingInput(asset_type="car", system="PRICE", asset_value=100000, down_payment=20000, months=12, monthly_rate=0.01, iof_scenario="none")
    result = calculate_schedule(data)
    payments = [row["payment"] for row in result["schedule"]]
    assert max(payments) - min(payments) <= 0.04
    assert result["total_interest"] > 0
    assert result["schedule"][-1]["balance"] == 0


def test_sac_payment_decreases_and_balance_zero():
    data = FinancingInput(asset_type="real_estate", system="SAC", asset_value=300000, down_payment=60000, months=24, monthly_rate=0.008, iof_scenario="none")
    result = calculate_schedule(data)
    assert result["first_payment"] > result["last_payment"]
    assert result["schedule"][-1]["balance"] == 0
    assert result["math_validation"]["principal_repaid_matches_principal"] is True


def test_cet_is_greater_than_nominal_when_costs_exist():
    data = FinancingInput(asset_type="car", system="PRICE", asset_value=80000, down_payment=16000, months=60, monthly_rate=0.0149, admin_fee=900, insurance_monthly=120, mip_monthly=0, dfi_monthly=0)
    result = calculate_schedule(data)
    assert result["estimated_cet_monthly"] > result["monthly_rate"]
    assert result["iof_amount"] > 0
    assert result["principal_with_costs"] > result["financed_amount"]


def test_income_commitment_and_risk_are_returned():
    data = FinancingInput(asset_type="motorcycle", system="PRICE", asset_value=30000, down_payment=6000, months=48, monthly_rate=0.018, monthly_income=5000, max_income_commitment_pct=0.30)
    result = calculate_schedule(data)
    assert result["income_commitment_pct"] is not None
    assert result["risk_level"] in {"baixo", "medio", "alto"}
    assert 0 <= result["risk_score"] <= 100


def test_zero_rate_price_equals_principal_over_months():
    assert round(price_payment(12000, 0, 12), 2) == 1000.00


def test_total_installments_matches_schedule_sum_and_validation_block():
    data = FinancingInput(asset_type="car", system="PRICE", asset_value=90000, down_payment=18000, months=36, monthly_rate=0.015, admin_fee=700, operational_fee=250, appraisal_fee=350, registry_fee=200, insurance_monthly=80)
    result = calculate_schedule(data)
    assert round(sum(row["payment"] for row in result["schedule"]), 2) == result["total_installments"]
    assert result["math_validation"]["final_balance_zero"] is True
    assert result["math_validation"]["principal_repaid_matches_principal"] is True
    assert result["total_cost"] == round(result["down_payment"] + result["total_installments"], 2)


def test_cet_components_are_separated():
    data = FinancingInput(asset_type="real_estate", system="SAC", asset_value=250000, down_payment=50000, months=120, monthly_rate=0.009, admin_fee=1000, operational_fee=500, appraisal_fee=800, registry_fee=1200, insurance_monthly=60, mip_monthly=90, dfi_monthly=40)
    result = calculate_schedule(data)
    components = result["cet_components"]
    for key in ["interest_total", "iof_amount", "admin_fee", "operational_fee", "appraisal_fee", "registry_fee", "insurance_total", "mip_total", "dfi_total"]:
        assert key in components
    assert components["admin_fee"] == 1000.0
    assert components["mip_total"] == 10800.0


def test_iof_multiple_scenarios():
    assert calculate_iof(__import__('decimal').Decimal('10000'), 12, 'none') == 0
    assert calculate_iof(__import__('decimal').Decimal('10000'), 12, 'pf_real_estate_exempt') == 0
    assert calculate_iof(__import__('decimal').Decimal('10000'), 12, 'custom', 0.01) == __import__('decimal').Decimal('100.00')


def test_internal_validator_rejects_invalid_down_payment():
    with pytest.raises(ValueError):
        calculate_schedule(FinancingInput(asset_type="car", system="PRICE", asset_value=50000, down_payment=50000, months=12, monthly_rate=0.01))


def test_zero_tolerance_validation_flags_are_exact():
    data = FinancingInput(
        asset_type="car",
        system="PRICE",
        asset_value=123456.78,
        down_payment=23456.78,
        months=37,
        monthly_rate=0.0137,
        admin_fee=777.77,
        operational_fee=123.45,
        appraisal_fee=222.22,
        registry_fee=333.33,
        insurance_monthly=88.88,
        iof_scenario="pf_auto",
    )
    result = calculate_schedule(data)
    validation = result["math_validation"]
    assert validation["zero_tolerance_enabled"] is True
    assert validation["final_balance"] == 0
    assert validation["sum_installments"] == validation["stored_total_installments"]
    assert validation["down_payment_plus_installments"] == validation["stored_total_cost"]
    assert validation["principal_repaid"] == validation["principal_with_costs"]


def test_calculation_audit_is_returned_for_bank_review():
    result = calculate_schedule(FinancingInput(asset_type="car", system="SAC", asset_value=70000, down_payment=14000, months=24, monthly_rate=0.012))
    audit = result["calculation_audit"]
    assert any("ROUND_HALF_EVEN" in line for line in audit)
    assert any("Validação matemática zero tolerância aprovada" in line for line in audit)


def test_extreme_long_real_estate_case_still_closes_balance():
    result = calculate_schedule(
        FinancingInput(
            asset_type="real_estate",
            system="PRICE",
            asset_value=1_200_000,
            down_payment=120_000,
            months=420,
            monthly_rate=0.0099,
            mip_monthly=350,
            dfi_monthly=110,
            appraisal_fee=3500,
            registry_fee=8500,
            iof_scenario="pf_real_estate_exempt",
        )
    )
    assert result["schedule"][-1]["balance"] == 0
    assert result["math_validation"]["principal_repaid_matches_principal"] is True
    assert result["estimated_cet_annual"] > result["annual_effective_rate"]

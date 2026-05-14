from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator

AssetType = Literal["car", "motorcycle", "real_estate"]
AmortizationSystem = Literal["SAC", "PRICE"]
IOFScenario = Literal["pf_auto", "pf_real_estate_exempt", "custom", "none"]


class FinancingSimulationRequest(BaseModel):
    asset_type: AssetType
    system: AmortizationSystem
    asset_value: float = Field(gt=0, le=100_000_000)
    down_payment: float = Field(ge=0)
    months: int = Field(ge=1, le=420)
    monthly_rate: float = Field(ge=0, le=0.20)
    monthly_income: float | None = Field(default=None, gt=0)
    max_income_commitment_pct: float = Field(default=0.30, gt=0, le=1)
    iof_scenario: IOFScenario = "pf_auto"
    iof_rate: float | None = Field(default=None, ge=0, le=0.20)
    admin_fee: float = Field(default=0.0, ge=0)
    operational_fee: float = Field(default=0.0, ge=0)
    appraisal_fee: float = Field(default=0.0, ge=0)
    registry_fee: float = Field(default=0.0, ge=0)
    insurance_monthly: float = Field(default=0.0, ge=0)
    mip_monthly: float = Field(default=0.0, ge=0)
    dfi_monthly: float = Field(default=0.0, ge=0)
    include_optional_insurance: bool = True

    @model_validator(mode="after")
    def validate_values(self) -> "FinancingSimulationRequest":
        if self.down_payment >= self.asset_value:
            raise ValueError("A entrada deve ser menor que o valor do bem")
        if self.iof_scenario == "custom" and self.iof_rate is None:
            raise ValueError("iof_rate é obrigatório quando iof_scenario=custom")
        return self


class FinancingCompareItem(BaseModel):
    bank_name: str = Field(min_length=1, max_length=120)
    monthly_rate: float = Field(ge=0, le=0.20)
    admin_fee: float = Field(default=0.0, ge=0)
    operational_fee: float = Field(default=0.0, ge=0)
    appraisal_fee: float = Field(default=0.0, ge=0)
    registry_fee: float = Field(default=0.0, ge=0)
    insurance_monthly: float = Field(default=0.0, ge=0)
    mip_monthly: float = Field(default=0.0, ge=0)
    dfi_monthly: float = Field(default=0.0, ge=0)
    iof_scenario: IOFScenario = "pf_auto"
    iof_rate: float | None = Field(default=None, ge=0, le=0.20)
    system: AmortizationSystem = "PRICE"


class FinancingCompareRequest(BaseModel):
    base: FinancingSimulationRequest
    offers: list[FinancingCompareItem] = Field(min_length=1, max_length=20)


class StrategyRequest(BaseModel):
    base: FinancingSimulationRequest
    wait_months: int = Field(default=12, ge=1, le=120)
    expected_asset_appreciation_monthly: float = Field(default=0.003, ge=-0.05, le=0.10)
    monthly_saving_capacity: float = Field(default=0.0, ge=0)


class InstallmentOut(BaseModel):
    month: int
    opening_balance: float
    payment: float
    base_payment: float
    amortization: float
    interest: float
    insurance: float
    mip: float
    dfi: float
    monthly_costs: float
    accumulated_interest: float
    accumulated_amortization: float
    balance: float


class FinancingSimulationResponse(BaseModel):
    asset_type: AssetType
    system: AmortizationSystem
    asset_value: float
    down_payment: float
    financed_amount: float
    principal_with_costs: float
    months: int
    monthly_rate: float
    annual_effective_rate: float
    estimated_cet_monthly: float
    estimated_cet_annual: float
    iof_scenario: IOFScenario
    iof_amount: float
    credit_one_time_costs: float
    cet_components: dict[str, float]
    admin_fee: float
    operational_fee: float
    appraisal_fee: float
    registry_fee: float
    insurance_total: float
    total_installments: float
    total_cost: float
    total_financed_cost: float
    total_interest: float
    first_payment: float
    last_payment: float
    average_payment: float
    income_commitment_pct: float | None
    ltv_pct: float
    risk_level: str
    risk_score: int
    approved: bool | None
    approval_reason: str | None
    comparison_save_more_down_payment: dict[str, float]
    schedule: list[InstallmentOut]
    math_validation: dict[str, float | bool]
    calculation_audit: list[str]
    disclaimer: str

    core_finance_context: dict | None = None

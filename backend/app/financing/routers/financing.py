from __future__ import annotations

import logging
from dataclasses import asdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.shared.auth import AuthenticatedUser, require_authenticated_user
from backend.app.financing.models import FinancingHistory, FinancingPreset, FinancingSimulation
from backend.app.financing.schemas import FinancingCompareRequest, FinancingSimulationRequest, FinancingSimulationResponse, StrategyRequest
from backend.app.financing.services.calculator import FinancingInput, calculate_schedule
from backend.app.financing.services.presets import DEFAULT_PRESETS
from backend.app.core.services.personal_finance import get_core_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/financing", tags=["Financing"])


def _to_input(payload: FinancingSimulationRequest) -> FinancingInput:
    return FinancingInput(**payload.model_dump())


def _save_history(db: Session, user_id: int, event_type: str, payload: dict, simulation_id: int | None = None) -> None:
    db.add(FinancingHistory(user_id=user_id, simulation_id=simulation_id, event_type=event_type, payload_json=payload))


def _save_simulation(db: Session, user_id: int, result: dict, monthly_income: float | None) -> FinancingSimulation:
    row = FinancingSimulation(
        user_id=user_id,
        asset_type=result["asset_type"],
        system=result["system"],
        asset_value=result["asset_value"],
        down_payment=result["down_payment"],
        financed_amount=result["financed_amount"],
        principal_with_costs=result["principal_with_costs"],
        months=result["months"],
        monthly_rate=result["monthly_rate"],
        annual_effective_rate=result["annual_effective_rate"],
        estimated_cet_monthly=result["estimated_cet_monthly"],
        estimated_cet_annual=result["estimated_cet_annual"],
        iof_scenario=result.get("iof_scenario", "pf_auto"),
        iof_amount=result["iof_amount"],
        credit_one_time_costs=result["credit_one_time_costs"],
        cet_components_json=result["cet_components"],
        admin_fee=result["admin_fee"],
        operational_fee=result["operational_fee"],
        appraisal_fee=result["appraisal_fee"],
        registry_fee=result["registry_fee"],
        insurance_total=result["insurance_total"],
        total_installments=result["total_installments"],
        total_cost=result["total_cost"],
        total_financed_cost=result["total_financed_cost"],
        total_interest=result["total_interest"],
        first_payment=result["first_payment"],
        last_payment=result["last_payment"],
        average_payment=result["average_payment"],
        monthly_income=monthly_income,
        income_commitment_pct=result["income_commitment_pct"],
        ltv_pct=result["ltv_pct"],
        risk_level=result["risk_level"],
        risk_score=result["risk_score"],
        approved=result["approved"],
        approval_reason=result["approval_reason"],
        input_json=result["input_snapshot"],
        schedule_json=result["schedule"],
    )
    db.add(row)
    db.flush()
    _save_history(db, user_id, "simulation_created", {k: v for k, v in result.items() if k != "schedule"}, row.id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/simulate", response_model=FinancingSimulationResponse)
def simulate(payload: FinancingSimulationRequest, db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    user_id = auth.user_id

    # Integração core -> financing: se a renda não vier na requisição,
    # tenta usar a renda mensal estimada do módulo original de finanças pessoais.
    effective_payload = payload
    monthly_income = payload.monthly_income
    if monthly_income is None:
        core_summary = get_core_summary()
        estimated_income = core_summary.get("renda_mensal_estimada")
        if estimated_income:
            monthly_income = float(estimated_income)
            effective_payload = payload.model_copy(update={"monthly_income": monthly_income})

    result = calculate_schedule(_to_input(effective_payload))
    result["core_finance_context"] = get_core_summary()
    _save_simulation(db, user_id, result, monthly_income)
    logger.info("Simulação de financiamento salva: user_id=%s asset_type=%s system=%s", user_id, payload.asset_type, payload.system)
    return result

@router.get("/history")
def history(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    user_id = auth.user_id
    rows = db.query(FinancingSimulation).filter(FinancingSimulation.user_id == user_id).order_by(FinancingSimulation.created_at.desc()).limit(50).all()
    return {"history": [{
        "id": row.id,
        "asset_type": row.asset_type,
        "system": row.system,
        "asset_value": row.asset_value,
        "down_payment": row.down_payment,
        "financed_amount": row.financed_amount,
        "months": row.months,
        "monthly_rate": row.monthly_rate,
        "estimated_cet_annual": row.estimated_cet_annual,
        "iof_scenario": getattr(row, "iof_scenario", "pf_auto"),
        "total_cost": row.total_cost,
        "total_interest": row.total_interest,
        "first_payment": row.first_payment,
        "last_payment": row.last_payment,
        "average_payment": row.average_payment,
        "income_commitment_pct": row.income_commitment_pct,
        "ltv_pct": row.ltv_pct,
        "risk_level": row.risk_level,
        "risk_score": row.risk_score,
        "approved": row.approved,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]}


@router.get("/presets")
def presets(db: Session = Depends(get_db), auth: AuthenticatedUser = Depends(require_authenticated_user)):
    user_id = auth.user_id
    custom = db.query(FinancingPreset).filter(FinancingPreset.user_id == user_id).all()
    if not custom:
        return {"presets": DEFAULT_PRESETS, "scope": "template_defaults_not_persisted"}
    return {"presets": [{
        "asset_type": row.asset_type,
        "name": row.name,
        "bank_name": row.bank_name,
        "default_monthly_rate": row.default_monthly_rate,
        "max_income_commitment_pct": row.max_income_commitment_pct,
        "admin_fee": row.admin_fee,
        "operational_fee": row.operational_fee,
        "appraisal_fee": row.appraisal_fee,
        "registry_fee": row.registry_fee,
        "insurance_monthly": row.insurance_monthly,
        "mip_monthly": row.mip_monthly,
        "dfi_monthly": row.dfi_monthly,
        "is_default": row.is_default,
    } for row in custom], "scope": "user"}


@router.post("/compare")
def compare(payload: FinancingCompareRequest, auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    results = []
    base_data = payload.base.model_dump()
    for offer in payload.offers:
        data = {**base_data, **offer.model_dump(exclude={"bank_name"})}
        result = calculate_schedule(FinancingInput(**data))
        results.append({"bank_name": offer.bank_name, **{k: result[k] for k in ["system", "monthly_rate", "estimated_cet_annual", "total_cost", "total_interest", "first_payment", "last_payment", "average_payment", "risk_level", "risk_score", "approved"]}})
    results.sort(key=lambda item: item["total_cost"])
    return {"comparison": results, "best_offer": results[0] if results else None}


@router.post("/strategy")
def strategy(payload: StrategyRequest, auth: AuthenticatedUser = Depends(require_authenticated_user)):
    auth.user_id
    now_result = calculate_schedule(_to_input(payload.base))
    future_asset_value = payload.base.asset_value * ((1 + payload.expected_asset_appreciation_monthly) ** payload.wait_months)
    future_down_payment = min(future_asset_value - 1, payload.base.down_payment + payload.monthly_saving_capacity * payload.wait_months)
    future_payload = payload.base.model_copy(update={"asset_value": future_asset_value, "down_payment": future_down_payment})
    future_result = calculate_schedule(_to_input(future_payload))
    return {
        "buy_now": {k: now_result[k] for k in ["asset_value", "down_payment", "financed_amount", "total_cost", "total_interest", "first_payment", "estimated_cet_annual", "risk_level", "approved"]},
        "wait": {k: future_result[k] for k in ["asset_value", "down_payment", "financed_amount", "total_cost", "total_interest", "first_payment", "estimated_cet_annual", "risk_level", "approved"]},
        "delta_total_cost_wait_minus_now": round(future_result["total_cost"] - now_result["total_cost"], 2),
        "delta_interest_wait_minus_now": round(future_result["total_interest"] - now_result["total_interest"], 2),
    }

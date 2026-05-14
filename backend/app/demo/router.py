from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.settings import get_settings

router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_PAYLOAD = {
    "user": {"email": "demo@financeos.app", "name": "Usuário Demo", "plan": "premium"},
    "dashboard": {
        "saldo": 18450.75,
        "receitas_mes": 9200.00,
        "despesas_mes": 5430.35,
        "investimentos_mes": 1840.00,
        "saude_financeira": 86,
    },
    "expenses": [
        {"categoria": "Moradia", "valor": 1850.00},
        {"categoria": "Alimentação", "valor": 1180.50},
        {"categoria": "Investimentos", "valor": 1840.00},
        {"categoria": "Transporte", "valor": 620.00},
    ],
    "goals": [
        {"nome": "Reserva de emergência", "progresso": 74},
        {"nome": "Carteira de investimentos", "progresso": 58},
        {"nome": "Viagem", "progresso": 41},
    ],
}


@router.get("/payload")
def demo_payload():
    if not get_settings().demo_mode_enabled:
        raise HTTPException(status_code=404, detail="Modo demo desativado")
    return DEMO_PAYLOAD


@router.post("/reset")
def reset_demo():
    if not get_settings().demo_mode_enabled:
        raise HTTPException(status_code=404, detail="Modo demo desativado")
    return {"status": "ok", "detail": "Demo resetada para dados seguros de apresentação."}

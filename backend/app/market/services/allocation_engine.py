BASE_ALLOCATIONS = {
    "Conservador": {"acoes": 0.10, "fiis": 0.15, "etfs": 0.10, "bdrs": 0.05, "cripto": 0.00, "reserva": 0.60},
    "Moderado": {"acoes": 0.25, "fiis": 0.20, "etfs": 0.20, "bdrs": 0.10, "cripto": 0.05, "reserva": 0.20},
    "Arrojado": {"acoes": 0.35, "fiis": 0.15, "etfs": 0.20, "bdrs": 0.15, "cripto": 0.10, "reserva": 0.05},
}

def allocation_for_profile(amount: float, risk_profile: str, macro_context: dict | None = None):
    base = BASE_ALLOCATIONS.get(risk_profile, BASE_ALLOCATIONS["Moderado"]).copy()
    selic = (macro_context.get("selic") or {}).get("value") if macro_context else None
    if selic and selic >= 10 and risk_profile != "Arrojado":
        base["reserva"] += 0.05
        base["acoes"] = max(0, base["acoes"] - 0.03)
        base["cripto"] = max(0, base["cripto"] - 0.02)
    total = sum(base.values()) or 1
    return {k: round(amount * (v / total), 2) for k, v in base.items()}

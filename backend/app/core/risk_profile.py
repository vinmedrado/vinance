from __future__ import annotations

from enum import Enum
from typing import Any


class RiskProfile(str, Enum):
    CONSERVADOR = "CONSERVADOR"
    MODERADO = "MODERADO"
    ARROJADO = "ARROJADO"


_ALIASES = {
    "conservador": RiskProfile.CONSERVADOR,
    "conservative": RiskProfile.CONSERVADOR,
    "baixo": RiskProfile.CONSERVADOR,
    "baixa": RiskProfile.CONSERVADOR,
    "moderado": RiskProfile.MODERADO,
    "moderada": RiskProfile.MODERADO,
    "medium": RiskProfile.MODERADO,
    "medio": RiskProfile.MODERADO,
    "médio": RiskProfile.MODERADO,
    "arrojado": RiskProfile.ARROJADO,
    "arrojada": RiskProfile.ARROJADO,
    "agressivo": RiskProfile.ARROJADO,
    "agressiva": RiskProfile.ARROJADO,
    "aggressive": RiskProfile.ARROJADO,
    "alto": RiskProfile.ARROJADO,
    "alta": RiskProfile.ARROJADO,
}


def normalize_risk_profile(value: Any, default: RiskProfile = RiskProfile.MODERADO) -> RiskProfile:
    """Normaliza perfis usados pelo legado, dashboard, radar e investimentos.

    Esta é a fonte única para transformar entradas livres em um enum interno.
    Aceita conservador/moderado/arrojado e o alias agressivo -> arrojado.
    """
    if isinstance(value, RiskProfile):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return _ALIASES.get(normalized, default)


def risk_profile_label(value: Any) -> str:
    return normalize_risk_profile(value).value


def risk_profile_slug(value: Any) -> str:
    return normalize_risk_profile(value).value.lower()

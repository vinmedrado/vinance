from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

NEUTRAL_SCORE = 50


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _get(asset: Any, field: str) -> Any:
    if isinstance(asset, dict):
        return asset.get(field)
    return getattr(asset, field, None)


def _score_range(value: Any, *, low: Decimal, high: Decimal, higher_is_better: bool = True) -> int:
    decimal = _to_decimal(value)
    if decimal is None:
        return NEUTRAL_SCORE
    if high == low:
        return NEUTRAL_SCORE
    ratio = (decimal - low) / (high - low)
    ratio = max(Decimal("0"), min(Decimal("1"), ratio))
    if not higher_is_better:
        ratio = Decimal("1") - ratio
    return int((ratio * Decimal("100")).quantize(Decimal("1")))


def _score_bool(value: Any, true_score: int = 85, false_score: int = 45) -> int:
    if value is None:
        return NEUTRAL_SCORE
    return true_score if bool(value) else false_score


def _score_maturity(vencimento: Any) -> int:
    if vencimento is None:
        return NEUTRAL_SCORE
    if isinstance(vencimento, str):
        try:
            vencimento = date.fromisoformat(vencimento)
        except ValueError:
            return NEUTRAL_SCORE
    days = (vencimento - date.today()).days
    return _score_range(days, low=Decimal("30"), high=Decimal("1825"), higher_is_better=False)


def _finalize(asset: Any, asset_class: str, components: dict[str, int], required_fields: list[str], methodology: str) -> dict:
    missing = [field for field in required_fields if _get(asset, field) is None]
    score = int(round(sum(components.values()) / max(1, len(components))))
    score = max(0, min(100, score))
    reasons = [f"{name}: {value}/100" for name, value in components.items()]
    if missing:
        reasons.append("Dados ausentes pontuados como neutros (50/100).")
    return {
        "ticker": str(_get(asset, "ticker") or _get(asset, "nome") or _get(asset, "coin_id") or "N/D"),
        "name": _get(asset, "name") or _get(asset, "nome"),
        "asset_class": asset_class,
        "score": score,
        "reasons": reasons,
        "missing_fields": missing,
        "methodology": methodology,
    }


def score_fii(asset: Any) -> dict:
    fields = ["dy_12m", "pvp", "vacancia_fisica", "liquidez_diaria"]
    return _finalize(asset, "fii", {
        "dy_12m": _score_range(_get(asset, "dy_12m"), low=Decimal("0"), high=Decimal("12")),
        "pvp": _score_range(_get(asset, "pvp"), low=Decimal("0.6"), high=Decimal("1.4"), higher_is_better=False),
        "vacancia_fisica": _score_range(_get(asset, "vacancia_fisica"), low=Decimal("0"), high=Decimal("30"), higher_is_better=False),
        "liquidez_diaria": _score_range(_get(asset, "liquidez_diaria"), low=Decimal("0"), high=Decimal("2000000")),
    }, fields, "Score heurístico de FIIs: dividend yield, P/VP, vacância e liquidez.")


def score_acao(asset: Any) -> dict:
    fields = ["roe", "pl", "dy_12m", "divida_liq_ebitda", "volume_medio_diario"]
    return _finalize(asset, "acoes", {
        "roe": _score_range(_get(asset, "roe"), low=Decimal("0"), high=Decimal("25")),
        "pl": _score_range(_get(asset, "pl"), low=Decimal("5"), high=Decimal("35"), higher_is_better=False),
        "dy_12m": _score_range(_get(asset, "dy_12m"), low=Decimal("0"), high=Decimal("10")),
        "divida_liq_ebitda": _score_range(_get(asset, "divida_liq_ebitda"), low=Decimal("0"), high=Decimal("4"), higher_is_better=False),
        "volume_medio_diario": _score_range(_get(asset, "volume_medio_diario"), low=Decimal("0"), high=Decimal("100000000")),
    }, fields, "Score heurístico de ações: rentabilidade, valuation, dividendos, alavancagem e liquidez.")


def score_etf(asset: Any) -> dict:
    fields = ["taxa_adm", "tracking_error", "retorno_12m", "volume_medio_diario"]
    return _finalize(asset, "etf", {
        "taxa_adm": _score_range(_get(asset, "taxa_adm"), low=Decimal("0"), high=Decimal("2"), higher_is_better=False),
        "tracking_error": _score_range(_get(asset, "tracking_error"), low=Decimal("0"), high=Decimal("5"), higher_is_better=False),
        "retorno_12m": _score_range(_get(asset, "retorno_12m"), low=Decimal("-20"), high=Decimal("30")),
        "volume_medio_diario": _score_range(_get(asset, "volume_medio_diario"), low=Decimal("0"), high=Decimal("50000000")),
    }, fields, "Score heurístico de ETFs: custo, aderência ao índice, retorno e liquidez.")


def score_bdr(asset: Any) -> dict:
    fields = ["dy_12m", "volume_medio_diario_brl", "cotacao_cambio"]
    return _finalize(asset, "bdr", {
        "dy_12m": _score_range(_get(asset, "dy_12m"), low=Decimal("0"), high=Decimal("8")),
        "liquidez": _score_range(_get(asset, "volume_medio_diario_brl"), low=Decimal("0"), high=Decimal("20000000")),
        "volatilidade_proxy": NEUTRAL_SCORE,
        "risco_cambio": _score_range(_get(asset, "cotacao_cambio"), low=Decimal("3"), high=Decimal("8"), higher_is_better=False),
    }, fields, "Score heurístico de BDRs: dividendos, liquidez, proxy neutro de volatilidade e risco cambial.")


def score_cripto(asset: Any) -> dict:
    fields = ["market_cap_rank", "volume_24h_usd", "price_change_30d_pct", "ath_change_pct"]
    return _finalize(asset, "cripto", {
        "market_cap_rank": _score_range(_get(asset, "market_cap_rank"), low=Decimal("1"), high=Decimal("200"), higher_is_better=False),
        "volume_24h_usd": _score_range(_get(asset, "volume_24h_usd"), low=Decimal("0"), high=Decimal("1000000000")),
        "price_change_30d_pct": _score_range(_get(asset, "price_change_30d_pct"), low=Decimal("-50"), high=Decimal("50")),
        "ath_change_pct": _score_range(_get(asset, "ath_change_pct"), low=Decimal("-90"), high=Decimal("0")),
    }, fields, "Score heurístico de cripto: rank, volume, momentum de 30 dias e distância do ATH.")


def score_renda_fixa(asset: Any) -> dict:
    fields = ["taxa_total_equiv", "liquidez_dias", "garantia_fgc", "vencimento"]
    return _finalize(asset, "renda_fixa", {
        "taxa_total_equiv": _score_range(_get(asset, "taxa_total_equiv"), low=Decimal("80"), high=Decimal("130")),
        "liquidez_dias": _score_range(_get(asset, "liquidez_dias"), low=Decimal("0"), high=Decimal("720"), higher_is_better=False),
        "garantia_fgc": _score_bool(_get(asset, "garantia_fgc")),
        "vencimento": _score_maturity(_get(asset, "vencimento")),
    }, fields, "Score heurístico de renda fixa: taxa, liquidez, garantia FGC e vencimento.")


SCORERS = {
    "fii": score_fii,
    "acoes": score_acao,
    "etf": score_etf,
    "bdr": score_bdr,
    "cripto": score_cripto,
    "renda_fixa": score_renda_fixa,
}


def score_asset(asset: Any, asset_class: str) -> dict:
    scorer = SCORERS.get(asset_class)
    if scorer is None:
        raise ValueError(f"unsupported asset class: {asset_class}")
    return scorer(asset)


def rank_assets(asset_class: str, assets: list[Any], *, limit: int = 10) -> list[dict]:
    scored = [score_asset(asset, asset_class) for asset in assets]
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

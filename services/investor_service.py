
from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text

from db.database import SessionLocal

MARKET_LABELS = {
    "equity": "Ações", "acao": "Ações", "acoes": "Ações", "stock": "Ações",
    "fii": "FIIs", "fiis": "FIIs", "fund": "FIIs", "reit": "FIIs",
    "etf": "ETFs", "etfs": "ETFs",
    "bdr": "BDRs", "bdrs": "BDRs",
    "crypto": "Cripto", "cripto": "Cripto", "cryptocurrency": "Cripto",
    "fixed_income": "Renda Fixa", "forex": "Câmbio",
}

INVESTOR_MARKETS = ["Ações", "FIIs", "ETFs", "BDRs", "Cripto", "Renda Fixa", "Câmbio"]


def _session():
    return SessionLocal()


def _json_load(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_market(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in MARKET_LABELS:
        return MARKET_LABELS[raw]
    if "fii" in raw or "reit" in raw:
        return "FIIs"
    if "etf" in raw:
        return "ETFs"
    if "bdr" in raw:
        return "BDRs"
    if "crypto" in raw or "cripto" in raw or "btc" in raw:
        return "Cripto"
    if "forex" in raw or "fx" in raw:
        return "Câmbio"
    return "Ações"


def load_catalog(tenant_id: str) -> pd.DataFrame:
    with _session() as db:
        try:
            rows = db.execute(
                text("""
                    SELECT ticker,
                           COALESCE(asset_class, class, type, market, 'equity') AS asset_class,
                           COALESCE(data_quality_score, quality_score, score_quality, quality, 50) AS data_quality_score,
                           COALESCE(reliability_status, status, validation_status, 'unknown') AS reliability_status,
                           COALESCE(name, asset_name, description, ticker) AS asset_name
                    FROM asset_catalog
                    WHERE tenant_id=:tenant_id
                """),
                {"tenant_id": tenant_id},
            ).mappings().all()
        except Exception:
            rows = []
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["ticker", "asset_class", "data_quality_score", "reliability_status", "asset_name", "market"])
    df["ticker"] = df["ticker"].astype(str)
    df["data_quality_score"] = pd.to_numeric(df["data_quality_score"], errors="coerce").fillna(50).clip(0, 100)
    df["market"] = df["asset_class"].apply(normalize_market)
    return df.drop_duplicates(subset=["ticker"])


def load_predictions(tenant_id: str, limit: int = 500) -> pd.DataFrame:
    with _session() as db:
        try:
            rows = db.execute(
                text("""
                    SELECT *
                    FROM ml_predictions
                    WHERE tenant_id=:tenant_id
                    ORDER BY prediction_date DESC, predicted_score DESC, confidence DESC
                    LIMIT :limit
                """),
                {"tenant_id": tenant_id, "limit": int(limit)},
            ).mappings().all()
        except Exception:
            # Compatibilidade com tabela antiga sem tenant_id: não retorna dados globais para investidor.
            rows = []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["predicted_score"] = pd.to_numeric(df["predicted_score"], errors="coerce").fillna(0)
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
    parsed_features = df["features_json"].apply(_json_load)
    parsed_exp = df["explanation_json"].apply(_json_load)
    df["feature_quality"] = parsed_features.apply(lambda x: x.get("data_quality_score"))
    df["feature_reliability"] = parsed_features.apply(lambda x: x.get("reliability_status") or "unknown")
    df["ml_recommendation"] = parsed_exp.apply(lambda x: x.get("recommendation"))
    df["simple_reason_raw"] = parsed_exp.apply(lambda x: x.get("summary") or "")
    df["data_quality_score"] = pd.to_numeric(df["feature_quality"], errors="coerce").fillna(50).clip(0, 100)
    df["reliability_status"] = df["feature_reliability"].fillna("unknown")
    return df


def _normalize_ml_score(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if -1 <= v <= 1:
        if v < 0:
            return max(0, min(100, 50 + v * 100))
        return max(0, min(100, v * 100))
    return max(0, min(100, v))


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.70:
        return "Alta"
    if confidence >= 0.50:
        return "Média"
    return "Baixa"


def _risk_from_asset(row: pd.Series) -> str:
    quality = float(row.get("data_quality_score") or 0)
    confidence = float(row.get("confidence") or 0)
    reliability = str(row.get("reliability_status") or "").lower()
    label = str(row.get("predicted_label") or "").lower()
    if quality < 45 or confidence < 0.35 or "invalid" in reliability or "weak" in reliability:
        return "Alto"
    if quality >= 70 and confidence >= 0.65 and label not in {"negative", "low", "0"}:
        return "Baixo"
    return "Médio"


def final_classification(score_final: float, confidence: float, quality: float) -> str:
    if score_final >= 75 and confidence >= 0.70 and quality >= 65:
        return "Forte"
    if score_final >= 60 and confidence >= 0.55 and quality >= 45:
        return "Boa"
    if score_final >= 45 and quality >= 45:
        return "Neutra"
    return "Evitar"


def build_simple_explanation(asset: dict[str, Any]) -> str:
    classification = asset.get("classificacao") or asset.get("classification")
    risk = asset.get("risco") or asset.get("risk")
    confidence = asset.get("confidence_label")
    quality = float(asset.get("data_quality_score") or 0)

    parts = []
    if classification in {"Forte", "Boa"}:
        parts.append("Este ativo apresenta sinais positivos recentes")
    elif classification == "Neutra":
        parts.append("Este ativo apresenta sinais mistos e merece acompanhamento")
    else:
        parts.append("Este ativo apresenta sinais frágeis no momento")

    parts.append("com boa confiança na leitura atual" if confidence == "Alta" else "com confiança moderada" if confidence == "Média" else "com baixa confiança")
    parts.append("e dados confiáveis" if quality >= 65 else "e qualidade de dados aceitável" if quality >= 45 else "mas a qualidade dos dados é baixa")
    parts.append("O risco estimado é baixo." if risk == "Baixo" else "O risco estimado é moderado." if risk == "Médio" else "O risco estimado é alto.")
    return ", ".join(parts[:-1]) + ". " + parts[-1]


def get_opportunities(tenant_id: str, limit: int = 500, market: str | None = None) -> pd.DataFrame:
    pred = load_predictions(tenant_id, limit=limit)
    cat = load_catalog(tenant_id)
    if pred.empty:
        return pd.DataFrame()

    df = pred.merge(cat, on="ticker", how="left", suffixes=("", "_catalog"))
    if "market" not in df.columns:
        df["market"] = df.get("asset_class", "equity").apply(normalize_market)
    df["market"] = df["market"].fillna(df.get("asset_class", "equity")).apply(normalize_market)

    if "data_quality_score_catalog" in df.columns:
        df["data_quality_score"] = pd.to_numeric(df["data_quality_score_catalog"], errors="coerce").fillna(df["data_quality_score"]).clip(0, 100)
    if "reliability_status_catalog" in df.columns:
        df["reliability_status"] = df["reliability_status_catalog"].fillna(df["reliability_status"])

    df["ml_score_norm"] = df["predicted_score"].apply(_normalize_ml_score)
    df["confidence_norm"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0).clip(0, 1) * 100
    df["quality_norm"] = pd.to_numeric(df["data_quality_score"], errors="coerce").fillna(50).clip(0, 100)
    df["score_final"] = (0.45 * df["ml_score_norm"] + 0.35 * df["confidence_norm"] + 0.20 * df["quality_norm"]).round(1)
    df["confidence_label"] = df["confidence"].apply(_confidence_label)
    df["risco"] = df.apply(_risk_from_asset, axis=1)
    df["classificacao"] = df.apply(lambda r: final_classification(float(r["score_final"]), float(r["confidence"]), float(r["data_quality_score"])), axis=1)
    df.loc[df["ml_recommendation"].astype(str).str.lower() == "evitar", "classificacao"] = "Evitar"
    df["motivo"] = df.apply(lambda r: build_simple_explanation(r.to_dict()), axis=1)

    if market and market != "Todos":
        df = df[df["market"] == market]
    return df.sort_values(["score_final", "confidence", "data_quality_score"], ascending=False).reset_index(drop=True)


def market_summary(tenant_id: str) -> list[dict[str, Any]]:
    df = get_opportunities(tenant_id, limit=1000)
    rows = []
    for market in INVESTOR_MARKETS:
        g = df[df["market"] == market] if not df.empty else pd.DataFrame()
        if g.empty:
            rows.append({"market": market, "total": 0, "fortes": 0, "boas": 0, "risco_medio": "-", "score_medio": 0})
            continue
        risk_map = {"Baixo": 1, "Médio": 2, "Alto": 3}
        avg_risk = g["risco"].map(risk_map).fillna(2).mean()
        risco_medio = "Baixo" if avg_risk < 1.6 else "Médio" if avg_risk < 2.4 else "Alto"
        rows.append({"market": market, "total": int(len(g)), "fortes": int((g["classificacao"] == "Forte").sum()), "boas": int((g["classificacao"] == "Boa").sum()), "risco_medio": risco_medio, "score_medio": round(float(g["score_final"].mean()), 1)})
    return rows


def investor_overview(tenant_id: str) -> dict[str, Any]:
    try:
        from services.portfolio_service import get_portfolio_summary
        portfolio = get_portfolio_summary(tenant_id)
        patrimonio_total = portfolio.get("total_brl")
    except Exception:
        patrimonio_total = None

    df = get_opportunities(tenant_id, limit=1000)
    if df.empty:
        return {"patrimonio_total": patrimonio_total, "ativos": 0, "risco_medio": "-", "markets": market_summary(tenant_id), "has_data": False}

    risk_map = {"Baixo": 1, "Médio": 2, "Alto": 3}
    avg_risk = df["risco"].map(risk_map).fillna(2).mean()
    risco_medio = "Baixo" if avg_risk < 1.6 else "Médio" if avg_risk < 2.4 else "Alto"
    return {
        "patrimonio_total": patrimonio_total,
        "ativos": int(df["ticker"].nunique()),
        "risco_medio": risco_medio,
        "markets": market_summary(tenant_id),
        "has_data": True,
        "top_score": round(float(df["score_final"].max()), 1),
        "strong_count": int((df["classificacao"] == "Forte").sum()),
    }

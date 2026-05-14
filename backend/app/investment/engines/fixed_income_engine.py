from __future__ import annotations

from datetime import datetime, timezone


class FixedIncomeEngine:
    asset_class = "renda_fixa"

    def analyze_product(self, product: dict) -> dict:
        rate = float(product.get("rate") or 0)
        liquidity_days = int(product.get("liquidity_days") or 0)
        indexer = str(product.get("indexer") or "").upper()
        guarantee = str(product.get("guarantee_type") or "")
        maturity = product.get("maturity_date")
        days_to_maturity = None
        if isinstance(maturity, datetime):
            base = maturity if maturity.tzinfo else maturity.replace(tzinfo=timezone.utc)
            days_to_maturity = max((base - datetime.now(timezone.utc)).days, 0)
        risk = "baixo" if liquidity_days <= 1 and ("FGC" in guarantee.upper() or "TESOURO" in guarantee.upper()) else "medio"
        if liquidity_days > 720 or not guarantee:
            risk = "alto"
        reasons = [
            "Renda fixa foi analisada por taxa, prazo, liquidez e segurança do emissor/garantia.",
            f"Indexador identificado: {indexer or 'não informado'}.",
        ]
        if liquidity_days > 30:
            reasons.append("Liquidez não imediata: este produto não deve substituir reserva de emergência.")
        return {
            "asset_class": self.asset_class,
            "symbol": product.get("name"),
            "risk": risk,
            "risk_text": {"baixo": "baixo risco dentro de renda fixa", "medio": "risco moderado dentro de renda fixa", "alto": "alto risco dentro de renda fixa"}[risk],
            "metrics": {
                "rate": rate,
                "indexer": indexer,
                "liquidity_days": liquidity_days,
                "days_to_maturity": days_to_maturity,
                "guarantee_type": guarantee,
                "minimum_investment": float(product.get("minimum_investment") or 0),
            },
            "explanation": reasons,
            "portfolio_role": "preservação de capital, caixa planejado e reserva conforme liquidez",
            "disclaimer": "Análise educacional, sem promessa de ganho e sem recomendação individualizada.",
        }

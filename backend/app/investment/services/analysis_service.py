from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.market.models import Asset, AssetPrice
from backend.app.investment.models import AssetDividend, FixedIncomeProduct
from backend.app.investment.engines.fii_engine import FIIEngine
from backend.app.investment.engines.stock_engine import StockEngine
from backend.app.investment.engines.etf_engine import ETFEngine
from backend.app.investment.engines.bdr_engine import BDREngine
from backend.app.investment.engines.crypto_engine import CryptoEngine
from backend.app.investment.engines.fixed_income_engine import FixedIncomeEngine
from backend.app.investment.engines.lci_lca_engine import LCILCAEngine

ENGINE_BY_CLASS = {
    "fii": FIIEngine(),
    "fiis": FIIEngine(),
    "acao": StockEngine(),
    "acoes": StockEngine(),
    "stock": StockEngine(),
    "etf": ETFEngine(),
    "etfs": ETFEngine(),
    "bdr": BDREngine(),
    "bdrs": BDREngine(),
    "cripto": CryptoEngine(),
    "crypto": CryptoEngine(),
}


class InvestmentAnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_asset_class(self, asset_class: str) -> dict:
        cls = asset_class.lower().strip()
        if cls in ("renda_fixa", "fixed_income", "tesouro", "cdb"):
            return self._analyze_fixed_income(["Tesouro", "CDB", "Renda Fixa"])
        if cls in ("lci_lca", "lci", "lca"):
            return self._analyze_lci_lca()
        engine = ENGINE_BY_CLASS.get(cls)
        if engine is None:
            return {"asset_class": asset_class, "analyses": [], "message": "Classe de ativo ainda não suportada pelo motor multiativos."}
        assets = self.db.query(Asset).filter(Asset.asset_class.in_([cls, cls.rstrip('s')])).all()
        analyses = []
        for asset in assets:
            prices = [row.close for row in self.db.query(AssetPrice).filter(AssetPrice.symbol == asset.symbol).order_by(AssetPrice.date.asc()).all()]
            dividends = [row.amount for row in self.db.query(AssetDividend).filter(AssetDividend.symbol == asset.symbol).order_by(AssetDividend.date.asc()).all()]
            analyses.append(engine.analyze(asset.symbol, prices, dividends))
        return {
            "asset_class": cls,
            "comparison_rule": "Os ativos foram analisados apenas dentro da mesma classe. Não existe ranking único entre classes diferentes.",
            "analyses": analyses,
        }

    def _analyze_fixed_income(self, types: list[str]) -> dict:
        engine = FixedIncomeEngine()
        rows = self.db.query(FixedIncomeProduct).filter(FixedIncomeProduct.product_type.in_(types)).order_by(FixedIncomeProduct.updated_at.desc()).limit(100).all()
        analyses = [engine.analyze_product(self._product_to_dict(row)) for row in rows]
        return {"asset_class": "renda_fixa", "comparison_rule": "Renda fixa é analisada por taxa, prazo, liquidez e segurança; não é comparada com renda variável.", "analyses": analyses}

    def _analyze_lci_lca(self) -> dict:
        engine = LCILCAEngine()
        rows = self.db.query(FixedIncomeProduct).filter(FixedIncomeProduct.product_type.in_(["LCI", "LCA"])).order_by(FixedIncomeProduct.updated_at.desc()).limit(100).all()
        analyses = [engine.analyze_product(self._product_to_dict(row)) for row in rows]
        return {"asset_class": "lci_lca", "comparison_rule": "LCI/LCA é avaliada separadamente por isenção, carência, prazo e liquidez.", "analyses": analyses}

    @staticmethod
    def _product_to_dict(row: FixedIncomeProduct) -> dict:
        return {
            "issuer": row.issuer,
            "product_type": row.product_type,
            "name": row.name,
            "indexer": row.indexer,
            "rate": row.rate,
            "maturity_date": row.maturity_date,
            "liquidity_days": row.liquidity_days,
            "guarantee_type": row.guarantee_type,
            "minimum_investment": row.minimum_investment,
            "source": row.source,
        }

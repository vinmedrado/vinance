from __future__ import annotations

from .fixed_income_engine import FixedIncomeEngine


class LCILCAEngine(FixedIncomeEngine):
    asset_class = "lci_lca"

    def analyze_product(self, product: dict) -> dict:
        analysis = super().analyze_product(product)
        analysis["asset_class"] = self.asset_class
        analysis["explanation"].append("LCI/LCA costuma ter benefício fiscal para pessoa física, mas precisa respeitar carência e liquidez.")
        analysis["portfolio_role"] = "renda fixa isenta para objetivos com prazo definido, não como caixa imediato se houver carência"
        return analysis

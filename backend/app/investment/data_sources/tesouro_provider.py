from __future__ import annotations

from datetime import datetime
from typing import Any

import requests


class TesouroProvider:
    source = "tesouro_direto"
    URL = "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/service/api/treasurybondsinfo.json"

    def fetch_bonds(self) -> list[dict[str, Any]]:
        response = requests.get(self.URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("response", {}).get("TrsrBdTradgList", [])
        bonds: list[dict[str, Any]] = []
        for item in items:
            bond = item.get("TrsrBd", {})
            name = bond.get("nm") or bond.get("isinCd") or "Tesouro Direto"
            maturity_raw = bond.get("mtrtyDt")
            maturity = None
            if maturity_raw:
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        maturity = datetime.strptime(str(maturity_raw)[:19], fmt)
                        break
                    except ValueError:
                        pass
            bonds.append({
                "issuer": "Tesouro Nacional",
                "product_type": "Tesouro",
                "name": name,
                "indexer": self._infer_indexer(name),
                "rate": float(bond.get("anulInvstmtRate") or bond.get("anulRedRate") or 0),
                "maturity_date": maturity,
                "liquidity_days": 1,
                "guarantee_type": "Tesouro Nacional",
                "minimum_investment": float(bond.get("minInvstmtAmt") or 0),
                "source": self.source,
                "raw": bond,
            })
        return bonds

    @staticmethod
    def _infer_indexer(name: str) -> str:
        upper = name.upper()
        if "IPCA" in upper:
            return "IPCA"
        if "SELIC" in upper:
            return "SELIC"
        return "PRE"

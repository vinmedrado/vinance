from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests


class BCBProvider:
    source = "BCB_SGS"
    # 11 = Selic meta; 432 pode ser usado em algumas bases como taxa Selic meta definida pelo Copom.
    DEFAULT_SERIES = {"selic": 11}

    def fetch_series(self, code: int, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"formato": "json"}
        if start:
            params["dataInicial"] = start.strftime("%d/%m/%Y")
        if end:
            params["dataFinal"] = end.strftime("%d/%m/%Y")
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        rows = []
        for item in response.json():
            rows.append({
                "date": datetime.strptime(item["data"], "%d/%m/%Y"),
                "value": float(str(item["valor"]).replace(",", ".")),
                "raw": item,
            })
        return rows

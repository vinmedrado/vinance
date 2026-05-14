from __future__ import annotations

from datetime import date
from typing import Any

import requests


class BcbSgsProvider:
    source = "BCB_SGS"
    base_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

    def get_series(self, code: str, name: str, start: str = "01/01/2015", end: str | None = None) -> list[dict[str, Any]]:
        end = end or date.today().strftime("%d/%m/%Y")
        params = {"formato": "json", "dataInicial": start, "dataFinal": end}
        response = requests.get(self.base_url.format(code=code), params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows: list[dict[str, Any]] = []
        for item in payload:
            dt_br = item.get("data")
            value = item.get("valor")
            if not dt_br or value is None:
                continue
            day, month, year = dt_br.split("/")
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "date": f"{year}-{month}-{day}",
                    "value": float(str(value).replace(",", ".")),
                    "source": self.source,
                    "raw_json": item,
                }
            )
        return rows

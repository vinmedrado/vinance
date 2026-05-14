from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


class FixedIncomeCSVImporter:
    REQUIRED = {"issuer", "product_type", "name", "indexer", "rate"}

    def parse_file(self, path: str | Path) -> list[dict[str, Any]]:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return self.parse_rows(csv.DictReader(fh))

    def parse_rows(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            normalized = {str(k).strip(): v for k, v in row.items()}
            missing = [col for col in self.REQUIRED if not normalized.get(col)]
            if missing:
                raise ValueError(f"Linha {idx}: colunas obrigatórias ausentes: {', '.join(missing)}")
            maturity = normalized.get("maturity_date") or normalized.get("vencimento")
            parsed.append({
                "issuer": str(normalized["issuer"]).strip(),
                "product_type": str(normalized["product_type"]).strip(),
                "name": str(normalized["name"]).strip(),
                "indexer": str(normalized["indexer"]).strip().upper(),
                "rate": float(str(normalized["rate"]).replace(",", ".")),
                "maturity_date": datetime.fromisoformat(maturity) if maturity else None,
                "liquidity_days": int(float(normalized.get("liquidity_days") or 0)),
                "guarantee_type": normalized.get("guarantee_type") or "FGC/Tesouro conforme produto",
                "minimum_investment": float(str(normalized.get("minimum_investment") or 0).replace(",", ".")),
                "source": "csv_manual",
                "raw": normalized,
            })
        return parsed

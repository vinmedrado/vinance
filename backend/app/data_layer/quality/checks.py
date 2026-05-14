from __future__ import annotations

from datetime import date
from collections import Counter


def validate_price_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    if not rows:
        return ["Nenhum dado de preço retornado."]
    dates = [row.get("date") for row in rows]
    duplicates = [dt for dt, count in Counter(dates).items() if dt and count > 1]
    if duplicates:
        errors.append(f"Datas duplicadas detectadas: {duplicates[:5]}")
    today = date.today().isoformat()
    for idx, row in enumerate(rows):
        if row.get("date") and row["date"] > today:
            errors.append(f"Linha {idx}: data futura {row['date']}")
        for field in ("open", "high", "low", "close", "adjusted_close"):
            value = row.get(field)
            if value is not None and value < 0:
                errors.append(f"Linha {idx}: {field} negativo ({value})")
        volume = row.get("volume")
        if volume is not None and volume < 0:
            errors.append(f"Linha {idx}: volume negativo ({volume})")
    return errors


def validate_macro_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    if not rows:
        return ["Nenhum dado macro retornado."]
    today = date.today().isoformat()
    for idx, row in enumerate(rows):
        if not row.get("name") or not row.get("date"):
            errors.append(f"Linha {idx}: name/date ausentes")
        if row.get("date") and row["date"] > today:
            errors.append(f"Linha {idx}: data futura {row['date']}")
        if row.get("value") is None:
            errors.append(f"Linha {idx}: value ausente")
    return errors


def only_critical(errors: list[str]) -> list[str]:
    return [err for err in errors if "Nenhum dado" not in err]

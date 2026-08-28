from __future__ import annotations

import asyncio
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.catalog.models import AssetCatalog  # noqa: E402
from backend.app.catalog.schemas import AssetCatalogCreate  # noqa: E402
from backend.app.core.database import AsyncSessionLocal  # noqa: E402

REQUIRED_COLUMNS = {
    "ticker",
    "name",
    "market",
    "sector",
    "segment",
    "currency",
    "exchange",
    "source",
    "is_active",
}
CATALOG_DIR = ROOT / "data" / "catalogs"


@dataclass(slots=True)
class SeedSummary:
    files_processed: int = 0
    inserted: int = 0
    updated: int = 0
    ignored: int = 0
    validation_errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "files_processed": self.files_processed,
            "inserted": self.inserted,
            "updated": self.updated,
            "ignored": self.ignored,
            "validation_errors": self.validation_errors,
        }


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim", "y"}


def validate_csv_columns(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"{path.name}: missing required columns: {', '.join(sorted(missing))}")


def iter_catalog_rows(path: Path):
    validate_csv_columns(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for line_number, row in enumerate(reader, start=2):
            yield line_number, row


def build_payload(row: dict[str, str]) -> AssetCatalogCreate:
    return AssetCatalogCreate(
        ticker=row.get("ticker", ""),
        name=row.get("name", ""),
        market=row.get("market", ""),
        sector=(row.get("sector") or None),
        segment=(row.get("segment") or None),
        currency=(row.get("currency") or None),
        exchange=(row.get("exchange") or None),
        source=(row.get("source") or None),
        is_active=parse_bool(row.get("is_active")),
    )


def collect_catalog_payloads(catalog_dir: Path = CATALOG_DIR) -> tuple[list[dict], SeedSummary]:
    summary = SeedSummary()
    payloads: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(catalog_dir.glob("*.csv")):
        summary.files_processed += 1
        try:
            rows = list(iter_catalog_rows(path))
        except ValueError as exc:
            summary.validation_errors += 1
            print(f"[validation-error] {exc}")
            continue

        for line_number, row in rows:
            try:
                payload = build_payload(row)
            except ValueError as exc:
                summary.validation_errors += 1
                print(f"[validation-error] {path.name}:{line_number}: {exc}")
                continue

            data = payload.normalized_payload()
            key = (data["ticker"], data["market"])
            if key in seen:
                summary.ignored += 1
                continue
            seen.add(key)
            payloads.append(data)
    return payloads, summary


async def upsert_catalog_from_csv(catalog_dir: Path = CATALOG_DIR) -> SeedSummary:
    payloads, summary = collect_catalog_payloads(catalog_dir)
    async with AsyncSessionLocal() as session:
        for data in payloads:
            result = await session.execute(
                select(AssetCatalog).where(
                    AssetCatalog.ticker == data["ticker"],
                    AssetCatalog.market == data["market"],
                )
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                session.add(AssetCatalog(**data))
                summary.inserted += 1
            else:
                changed = False
                for field, value in data.items():
                    if getattr(asset, field) != value:
                        setattr(asset, field, value)
                        changed = True
                if changed:
                    summary.updated += 1
                else:
                    summary.ignored += 1
        await session.commit()
    return summary


async def main() -> None:
    summary = await upsert_catalog_from_csv()
    print("Seed catalog summary:")
    for key, value in summary.as_dict().items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())

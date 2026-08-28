from __future__ import annotations

from backend.app.market.services.catalog_service import CatalogService


def test_catalog_service_import_contract() -> None:
    service = CatalogService()
    assert hasattr(service, "list_tickers")
    assert hasattr(service, "count_by_market")

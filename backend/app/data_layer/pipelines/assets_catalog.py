from __future__ import annotations

from backend.app.data_layer.catalog import CATALOG_ASSETS
from backend.app.data_layer.repositories.sqlite_repository import connect, ensure_patch6_schema, finish_log, start_log, upsert_asset


def run() -> dict:
    with connect() as conn:
        ensure_patch6_schema(conn)
        log_id = start_log(conn, "sync_assets_catalog", "catalog", "assets")
        inserted = updated = 0
        try:
            for asset in CATALOG_ASSETS:
                _, was_inserted = upsert_asset(conn, {**asset, "source": "catalog"})
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1
            finish_log(conn, log_id, "SUCCESS", inserted, updated, 0, f"Catálogo sincronizado: {inserted} inseridos, {updated} atualizados.")
            return {"status": "SUCCESS", "inserted": inserted, "updated": updated}
        except Exception as exc:
            finish_log(conn, log_id, "ERROR", inserted, updated, 0, error_message=str(exc))
            raise


if __name__ == "__main__":
    print(run())

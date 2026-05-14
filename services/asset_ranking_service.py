from __future__ import annotations

from db import pg_compat as dbcompat
from typing import Any

from services.asset_quality_service import ensure_asset_quality_columns


def _rows(conn: dbcompat.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = dbcompat.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_top_assets(conn: dbcompat.Connection, asset_class: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    ensure_asset_quality_columns(conn)
    sql = """
        SELECT ticker, name, asset_class, market, currency, api_status,
               preferred_source, last_source_used, source_priority,
               data_quality_score, validation_score, reliability_status,
               recommendation_tag, price_records, first_price_date, last_price_date
          FROM asset_catalog
         WHERE 1=1
    """
    params: list[Any] = []
    if asset_class and asset_class != "all":
        sql += " AND LOWER(asset_class)=LOWER(?)"
        params.append(asset_class)
    sql += " ORDER BY data_quality_score DESC, validation_score DESC, price_records DESC, ticker LIMIT ?"
    params.append(int(limit))
    return _rows(conn, sql, tuple(params))


def get_recommended_assets(conn: dbcompat.Connection, asset_class: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    ensure_asset_quality_columns(conn)
    sql = """
        SELECT ticker, name, asset_class, api_status, preferred_source, last_source_used,
               data_quality_score, reliability_status, recommendation_tag,
               price_records, first_price_date, last_price_date
          FROM asset_catalog
         WHERE recommendation_tag IN ('recommended', 'watchlist')
    """
    params: list[Any] = []
    if asset_class and asset_class != "all":
        sql += " AND LOWER(asset_class)=LOWER(?)"
        params.append(asset_class)
    sql += " ORDER BY data_quality_score DESC, validation_score DESC, price_records DESC LIMIT ?"
    params.append(int(limit))
    return _rows(conn, sql, tuple(params))


def get_assets_to_avoid(conn: dbcompat.Connection, limit: int = 20) -> list[dict[str, Any]]:
    ensure_asset_quality_columns(conn)
    return _rows(
        conn,
        """
        SELECT ticker, name, asset_class, api_status, preferred_source, last_source_used,
               data_quality_score, reliability_status, recommendation_tag, price_records, notes
          FROM asset_catalog
         WHERE recommendation_tag='avoid' OR reliability_status IN ('weak_data', 'invalid')
         ORDER BY data_quality_score ASC, ticker
         LIMIT ?
        """,
        (int(limit),),
    )


def get_catalog_summary(conn: dbcompat.Connection) -> dict[str, Any]:
    ensure_asset_quality_columns(conn)
    total = conn.execute("SELECT COUNT(*) FROM asset_catalog").fetchone()[0]
    by_rel = {r[0] or "unknown": r[1] for r in conn.execute("SELECT reliability_status, COUNT(*) FROM asset_catalog GROUP BY reliability_status")}
    by_rec = {r[0] or "pending": r[1] for r in conn.execute("SELECT recommendation_tag, COUNT(*) FROM asset_catalog GROUP BY recommendation_tag")}
    by_class = {r[0] or "unknown": r[1] for r in conn.execute("SELECT asset_class, COUNT(*) FROM asset_catalog GROUP BY asset_class")}
    by_status = {r[0] or "unknown": r[1] for r in conn.execute("SELECT api_status, COUNT(*) FROM asset_catalog GROUP BY api_status")}
    by_source = {r[0] or "sem_fonte": r[1] for r in conn.execute("SELECT COALESCE(last_source_used, preferred_source, 'sem_fonte'), COUNT(*) FROM asset_catalog GROUP BY COALESCE(last_source_used, preferred_source, 'sem_fonte')")}
    no_score = conn.execute("SELECT COUNT(*) FROM asset_catalog WHERE COALESCE(data_quality_score,0)=0 OR updated_quality_at IS NULL").fetchone()[0]
    last_quality = conn.execute("SELECT MAX(updated_quality_at) FROM asset_catalog").fetchone()[0]
    last_validation = conn.execute("SELECT MAX(last_validated_at) FROM asset_catalog").fetchone()[0]
    no_source = conn.execute("SELECT COUNT(*) FROM asset_catalog WHERE COALESCE(last_source_used, preferred_source, '')=''").fetchone()[0]
    return {
        "total": total,
        "by_reliability": by_rel,
        "by_recommendation": by_rec,
        "by_class": by_class,
        "by_status": by_status,
        "by_source": by_source,
        "no_score": no_score,
        "no_source": no_source,
        "last_quality_update": last_quality,
        "last_validation": last_validation,
    }

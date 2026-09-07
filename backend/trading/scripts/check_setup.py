from __future__ import annotations

from sqlalchemy import text

from ..config import get_settings
from ..storage.database import create_sync_engine


def main() -> None:
    settings = get_settings()
    print("Vinance Trading V2")
    print(f"Modo: {settings.trading_mode}")
    print(f"Ativos: {settings.trading_symbols}")
    print(f"Intervalo: {settings.trading_interval}")
    engine = create_sync_engine(settings.database_url)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Banco conectado com sucesso.")


if __name__ == "__main__":
    main()

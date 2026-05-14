from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ExternalAPIError(RuntimeError):
    pass


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
    retries: int = 2,
) -> dict[str, Any] | list[Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise ExternalAPIError(f"Resposta inválida da API externa em {url}") from exc
        except requests.Timeout as exc:
            last_error = exc
            logger.warning("Timeout API externa: url=%s tentativa=%s", url, attempt + 1)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text[:500] if exc.response is not None else ""
            last_error = exc
            logger.warning("HTTP API externa: url=%s status=%s body=%s", url, status, body)
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                break
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Falha API externa: url=%s tentativa=%s erro=%s", url, attempt + 1, exc)
        if attempt < retries:
            time.sleep(0.7 * (attempt + 1))
    raise ExternalAPIError(f"Erro ao consultar API externa: {url}. Último erro: {last_error}")

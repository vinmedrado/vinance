"""Helpers isolados para diagnóstico controlado de XHR do Status Invest.

Este módulo NÃO é provider operacional, NÃO acessa banco e NÃO integra Celery.
Ele existe apenas para confirmar payloads, headers e formato JSON antes da Fase 17 final.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

BASE_URL = "https://statusinvest.com.br"
ADVANCED_SEARCH_ENDPOINT = f"{BASE_URL}/category/advancedsearchresult"
RAW_OUTPUT_DIR = Path("temp/statusinvest")
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRIES = 1
DEFAULT_SLEEP_SECONDS = 1.0

LOGGER_NAME = "statusinvest_diagnostics"
logger = logging.getLogger(LOGGER_NAME)


@dataclass(frozen=True)
class DiagnosticResult:
    """Resultado resumido de uma chamada de diagnóstico."""

    url: str
    params: dict[str, Any]
    status_code: int | None
    elapsed_ms: float | None
    content_type: str | None
    response_size: int
    json_payload: Any | None
    error: str | None = None


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def browser_headers(referer: str) -> dict[str, str]:
    """Headers mínimos e conservadores, sem cookie fixo, proxy ou bypass anti-bot."""

    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer,
        "Origin": BASE_URL,
        "Connection": "keep-alive",
    }


def compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_advanced_search_params(search_payload: Mapping[str, Any], category_type: int) -> dict[str, str | int]:
    return {
        "search": compact_json(search_payload),
        "CategoryType": category_type,
    }


def build_final_url(url: str, params: Mapping[str, Any]) -> str:
    return f"{url}?{urlencode(params)}"


def request_json(
    *,
    url: str,
    params: Mapping[str, Any],
    referer: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> DiagnosticResult:
    headers = browser_headers(referer)
    final_url = build_final_url(url, params)
    last_error: str | None = None

    for attempt in range(1, retries + 2):
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
                response = client.get(url, params=params)
            elapsed_ms = (time.perf_counter() - start) * 1000
            content_type = response.headers.get("content-type", "")
            response_size = len(response.content or b"")

            logger.info("URL final: %s", str(response.url))
            logger.info("Params enviados: %s", json.dumps(dict(params), ensure_ascii=False))
            logger.info("Status code: %s", response.status_code)
            logger.info("Tempo de resposta: %.2f ms", elapsed_ms)
            logger.info("Content-Type: %s", content_type or "<não informado>")
            logger.info("Tamanho da resposta: %s bytes", response_size)

            if response.status_code in {403, 404, 429}:
                logger.warning(
                    "Resposta crítica %s recebida. 403=bloqueio/permissão, 404=endpoint ausente, 429=rate limit.",
                    response.status_code,
                )

            json_payload: Any | None = None
            parse_error: str | None = None
            if response.content:
                try:
                    json_payload = response.json()
                except ValueError as exc:
                    parse_error = f"Resposta não é JSON válido: {exc}"
                    logger.warning(parse_error)
                    logger.debug("Início da resposta não JSON: %r", response.text[:500])

            return DiagnosticResult(
                url=final_url,
                params=dict(params),
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                content_type=content_type,
                response_size=response_size,
                json_payload=json_payload,
                error=parse_error,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Falha na tentativa %s/%s após %.2f ms: %s",
                attempt,
                retries + 1,
                elapsed_ms,
                last_error,
            )
            if attempt <= retries:
                time.sleep(sleep_seconds * attempt)

    return DiagnosticResult(
        url=final_url,
        params=dict(params),
        status_code=None,
        elapsed_ms=None,
        content_type=None,
        response_size=0,
        json_payload=None,
        error=last_error or "Falha desconhecida",
    )


def summarize_json(payload: Any, *, max_rows: int = 3) -> dict[str, Any]:
    """Resumo seguro para logs: não despeja resposta inteira."""

    if payload is None:
        return {"type": "null", "row_count": 0, "first_fields": [], "sample": []}

    if isinstance(payload, list):
        sample = payload[:max_rows]
        first = payload[0] if payload and isinstance(payload[0], dict) else None
        return {
            "type": "list",
            "row_count": len(payload),
            "first_fields": list(first.keys())[:40] if first else [],
            "sample": sample,
        }

    if isinstance(payload, dict):
        # Muitas respostas usam { data: [...] } ou { list: [...] }.
        nested_lists = {
            key: len(value)
            for key, value in payload.items()
            if isinstance(value, list)
        }
        first_fields: list[str] = list(payload.keys())[:40]
        nested_sample: Any = None
        for value in payload.values():
            if isinstance(value, list) and value:
                nested_sample = value[:max_rows]
                if isinstance(value[0], dict):
                    first_fields.extend([f"nested.{k}" for k in list(value[0].keys())[:40]])
                break
        return {
            "type": "dict",
            "top_level_fields": list(payload.keys())[:80],
            "nested_list_sizes": nested_lists,
            "first_fields": first_fields[:80],
            "sample": nested_sample if nested_sample is not None else payload,
        }

    return {"type": type(payload).__name__, "value_preview": str(payload)[:500]}


def print_summary(title: str, result: DiagnosticResult) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(f"URL final: {result.url}")
    print(f"Params enviados: {json.dumps(result.params, ensure_ascii=False)}")
    print(f"Status code: {result.status_code}")
    print(f"Tempo de resposta: {result.elapsed_ms:.2f} ms" if result.elapsed_ms is not None else "Tempo de resposta: <indisponível>")
    print(f"Content-Type: {result.content_type}")
    print(f"Tamanho da resposta: {result.response_size} bytes")
    if result.error:
        print(f"Erro: {result.error}")
    summary = summarize_json(result.json_payload)
    print("Resumo JSON:")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str)[:6000])


def save_raw_if_requested(result: DiagnosticResult, *, prefix: str, save_raw: bool) -> Path | None:
    if not save_raw:
        return None
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RAW_OUTPUT_DIR / f"{prefix}_{timestamp}.json"
    payload = {
        "url": result.url,
        "params": result.params,
        "status_code": result.status_code,
        "elapsed_ms": result.elapsed_ms,
        "content_type": result.content_type,
        "response_size": result.response_size,
        "error": result.error,
        "json_payload": result.json_payload,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("Resposta raw salva em: %s", output_path)
    return output_path


def range_filter(min_value: float | int | None = None, max_value: float | int | None = None) -> dict[str, float | int | None]:
    return {"Item1": min_value, "Item2": max_value}


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--save-raw", action="store_true", help="Salva resposta bruta em temp/statusinvest/. Não salva por padrão.")
    parser.add_argument("--verbose", action="store_true", help="Habilita logs DEBUG.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout HTTP em segundos.")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Número de retries leves após falha de rede/timeout.")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS, help="Sleep base entre retries/chamadas.")
    return parser

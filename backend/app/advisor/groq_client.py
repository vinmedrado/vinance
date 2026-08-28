from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(slots=True)
class GroqResult:
    ok: bool
    content: str | None = None
    error: str | None = None


class GroqClient:
    def __init__(self, *, api_key: str | None = None, model: str | None = None, timeout: float = 20.0, max_retries: int = 2) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

    async def generate_response(self, messages: list[dict[str, str]]) -> GroqResult:
        if not self.api_key:
            logger.warning("groq_api_key_missing", extra={"component": "advisor.groq_client"})
            return GroqResult(ok=False, error="GROQ_API_KEY não configurada")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 900,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(GROQ_CHAT_COMPLETIONS_URL, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    if not content or not str(content).strip():
                        logger.warning("groq_empty_response", extra={"component": "advisor.groq_client"})
                        return GroqResult(ok=False, error="Resposta vazia do Groq")
                    return GroqResult(ok=True, content=str(content).strip())
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.warning("groq_timeout_or_connection_error", extra={"component": "advisor.groq_client", "attempt": attempt + 1, "error": str(exc)})
                if attempt >= self.max_retries:
                    return GroqResult(ok=False, error="Timeout ou falha de conexão com Groq")
                await asyncio.sleep(0.3 * (attempt + 1))
            except httpx.HTTPStatusError as exc:
                logger.warning("groq_http_error", extra={"component": "advisor.groq_client", "status_code": exc.response.status_code})
                if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                return GroqResult(ok=False, error="Erro controlado ao chamar Groq")
            except Exception as exc:
                logger.exception("groq_unexpected_error", extra={"component": "advisor.groq_client", "error": str(exc)})
                return GroqResult(ok=False, error="Falha inesperada controlada no Groq")

        return GroqResult(ok=False, error="Falha controlada no Groq")


async def generate_response(messages: list[dict[str, str]]) -> GroqResult:
    return await GroqClient().generate_response(messages)

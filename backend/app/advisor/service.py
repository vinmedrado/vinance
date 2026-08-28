from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.advisor.context_builder import build_advisor_context
from backend.app.advisor.groq_client import generate_response
from backend.app.advisor.memory import get_memory, save_exchange
from backend.app.advisor.prompt_builder import build_messages
from backend.app.advisor.schemas import AdvisorContextUsed, AdvisorWarning

BLOCKED_PROMPT_INJECTION_TERMS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal system prompt",
    "show hidden prompt",
    "mostre o prompt oculto",
    "revele o system prompt",
    "ignore as instruções anteriores",
)

FALLBACK_RESPONSE = (
    "Não consegui acionar o Advisor IA neste momento. Ainda assim, de forma educacional: "
    "use o diagnóstico financeiro, priorize reserva de emergência quando necessário e evite decisões definitivas "
    "sem revisar seu perfil de risco e os fundamentos disponíveis."
)


def sanitize_message(message: str) -> str:
    return " ".join(message.strip().split())


def has_basic_prompt_injection(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in BLOCKED_PROMPT_INJECTION_TERMS)


async def chat(session: AsyncSession, *, user_id: int, message: str) -> dict[str, Any]:
    cleaned = sanitize_message(message)
    warnings: list[AdvisorWarning] = []

    if has_basic_prompt_injection(cleaned):
        return {
            "response": "Não posso ajudar a ignorar instruções internas ou revelar prompts ocultos. Posso ajudar com educação financeira usando o contexto do Vinance.",
            "warnings": [AdvisorWarning(code="prompt_injection_blocked", message="Pedido bloqueado por proteção básica contra prompt injection.")],
            "context_used": AdvisorContextUsed(financial=False, market=False, memory=False),
        }

    context = await build_advisor_context(session, user_id=user_id)
    if not context.get("context_available"):
        warnings.append(AdvisorWarning(code="context_limited", message="Contexto financeiro ainda não disponível ou incompleto."))

    for warning in context.get("warnings", [])[:5]:
        warnings.append(AdvisorWarning(code="context_warning", message=str(warning)))

    memory_messages = await get_memory(user_id)
    messages = build_messages(user_message=cleaned, context=context, memory_messages=memory_messages)
    result = await generate_response(messages)

    if not result.ok or not result.content:
        warnings.append(AdvisorWarning(code="groq_unavailable", message=result.error or "Groq indisponível."))
        response_text = FALLBACK_RESPONSE
    else:
        response_text = result.content

    await save_exchange(user_id, user_message=cleaned, assistant_message=response_text)
    top_assets = context.get("top_assets_by_class") or {}
    return {
        "response": response_text,
        "warnings": warnings[:10],
        "context_used": AdvisorContextUsed(
            financial=bool(context.get("financial")),
            market=any(bool(items) for items in top_assets.values()),
            memory=bool(memory_messages),
        ),
    }

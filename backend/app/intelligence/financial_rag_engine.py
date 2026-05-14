from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


class FinancialRAGEngine:
    """Retrieval financeiro interno sem dependência paga.

    Usa score local por palavras-chave, entidade relacionada e recência. Foi pensado
    como fallback semântico seguro enquanto embeddings reais não forem habilitados.
    """

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-ZÀ-ÿ0-9_]+", (text or "").lower()) if len(t) > 2}

    @classmethod
    def build_documents(cls, context: dict[str, Any], conversation_memory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        org = context.get("organization_id")
        user = context.get("user_id")
        def add(kind: str, title: str, content: str, entity_id: str | None = None, weight: float = 1.0):
            if content:
                docs.append({"organization_id": org, "user_id": user, "kind": kind, "title": title, "content": content, "entity_id": entity_id, "weight": weight, "created_at": datetime.now(timezone.utc).isoformat()})
        situation = context.get("current_financial_situation", {}) or {}
        add("snapshot", "Situação financeira atual", f"Renda {situation.get('monthly_income',0)}; despesas {situation.get('total_expenses',0)}; razão de despesas {situation.get('expense_ratio',0)}; dívida {situation.get('debt_ratio',0)}", weight=1.3)
        add("health", "Score e fase financeira", str(context.get("health", {})), weight=1.2)
        add("budget", "Modelo financeiro recomendado", str(context.get("budget_advisor", {}) or context.get("recommended_model", "")), weight=1.15)
        add("memory", "Memória financeira", str(context.get("memory", {}) or context.get("contextual_memory", {})), weight=1.05)
        add("behavior", "Comportamento financeiro", str(context.get("behavior", {})), weight=1.0)
        add("forecast", "Forecast financeiro", str(context.get("forecast", {})), weight=0.9)
        for i, goal in enumerate(context.get("goals", []) or (context.get("dynamic_goals", {}) or {}).get("goals", []) or []):
            add("goal", f"Meta {goal.get('goal_type','financeira')}", str(goal), entity_id=str(goal.get("id", i)), weight=1.2)
        for i, alert in enumerate(context.get("alerts", []) or []):
            add("alert", "Alerta recente", str(alert), entity_id=str(i), weight=1.25)
        for i, step in enumerate(context.get("next_steps", []) or []):
            add("next_step", "Próximo passo", str(step), entity_id=str(i), weight=1.05)
        if conversation_memory:
            add("conversation_memory", "Resumo da conversa", conversation_memory.get("summary", ""), weight=1.1)
            for i, msg in enumerate(conversation_memory.get("recent_context", []) or []):
                add("advisor_message", f"Mensagem recente {i+1}", msg.get("content", ""), entity_id=str(i), weight=0.8)
        return docs

    @classmethod
    def retrieve(cls, question: str, context: dict[str, Any], conversation_memory: dict[str, Any] | None = None, *, top_k: int = 6) -> list[dict[str, Any]]:
        q_tokens = cls._tokens(question)
        docs = cls.build_documents(context, conversation_memory)
        scored = []
        for doc in docs:
            d_tokens = cls._tokens(" ".join([doc.get("title", ""), doc.get("content", "")]))
            overlap = len(q_tokens & d_tokens)
            relevance = overlap / max(len(q_tokens), 1)
            if doc["kind"] in {"snapshot", "health"}:
                relevance += 0.18
            score = round((relevance + 0.05) * float(doc.get("weight", 1.0)), 4)
            if score > 0.04:
                item = dict(doc)
                item["relevance_score"] = score
                scored.append(item)
        scored.sort(key=lambda d: d["relevance_score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def compact_for_llm(items: list[dict[str, Any]], max_chars: int = 2200) -> str:
        lines = []
        total = 0
        for item in items:
            line = f"- [{item.get('kind')}] {item.get('title')}: {item.get('content')}"
            line = line[:520]
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)

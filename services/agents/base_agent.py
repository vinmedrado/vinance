
from __future__ import annotations

import json
import os
from typing import Any


class BaseAgent:
    """
    BaseAgent com dois modos:
    - IA real OpenAI-compatible se OPENAI_API_KEY existir e dependência estiver disponível.
    - fallback local por regras simples quando não houver API.

    Agentes apenas analisam dados. Não executam trades, não alteram estratégia e não rodam código dinâmico.
    """

    name = "base"
    description = "Agente base"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        safe_context = self._sanitize_context(context)
        if self._has_llm():
            try:
                prompt = self.build_prompt(safe_context)
                response = self._call_llm(prompt)
                parsed = self.parse_response(response)
                return self.normalize_output(parsed)
            except Exception as exc:
                fallback = self.run_fallback(safe_context)
                fallback["mode"] = "fallback"
                fallback["llm_error"] = str(exc)
                return self.normalize_output(fallback)

        fallback = self.run_fallback(safe_context)
        fallback["mode"] = "fallback"
        return self.normalize_output(fallback)

    def build_prompt(self, context: dict[str, Any]) -> str:
        return (
            "Você é um agente financeiro interpretativo do FinanceOS. "
            "Responda em JSON válido com este formato: "
            "{agent,status,summary,insights,recommendations,metrics_used}. "
            "Insights devem ser objetos com priority high/medium/low, title, message e recommendation. "
            f"Contexto:\n{json.dumps(context, ensure_ascii=False, default=str)[:12000]}"
        )

    def parse_response(self, response: str) -> dict[str, Any]:
        text = (response or "").strip()
        try:
            return json.loads(text)
        except Exception:
            return {
                "agent": self.name,
                "status": "warning",
                "summary": text[:2000] or "Resposta de IA sem JSON estruturado.",
                "insights": [],
                "recommendations": [],
                "metrics_used": {},
            }

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": "warning",
            "summary": "Análise local indisponível para este agente.",
            "insights": [],
            "recommendations": [],
            "metrics_used": {},
        }

    def normalize_output(self, data: dict[str, Any]) -> dict[str, Any]:
        data = dict(data or {})
        data.setdefault("agent", self.name)
        data.setdefault("status", "warning")
        data.setdefault("summary", "")
        data.setdefault("insights", [])
        data.setdefault("recommendations", [])
        data.setdefault("metrics_used", {})
        data.setdefault("mode", data.get("mode") or ("llm" if self._has_llm() else "fallback"))

        normalized_insights = []
        for item in data.get("insights") or []:
            if isinstance(item, dict):
                normalized_insights.append({
                    "priority": item.get("priority") or "medium",
                    "title": item.get("title") or item.get("name") or "Insight",
                    "message": item.get("message") or item.get("summary") or str(item),
                    "recommendation": item.get("recommendation") or "",
                    "agent": data["agent"],
                })
            else:
                normalized_insights.append({
                    "priority": "medium",
                    "title": "Insight",
                    "message": str(item),
                    "recommendation": "",
                    "agent": data["agent"],
                })
        data["insights"] = normalized_insights

        recs = []
        for rec in data.get("recommendations") or []:
            recs.append(str(rec))
        data["recommendations"] = recs
        return data

    def make_insight(self, priority: str, title: str, message: str, recommendation: str = "") -> dict[str, Any]:
        return {
            "priority": priority,
            "title": title,
            "message": message,
            "recommendation": recommendation,
            "agent": self.name,
        }

    def _has_llm(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY"))

    def _call_llm(self, prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

        if not api_key:
            raise RuntimeError("API key não configurada.")

        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("Pacote openai não instalado; usando fallback local.") from exc

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Responda sempre em JSON válido. Não recomende execução automática de ordens."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return completion.choices[0].message.content or "{}"

    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        blocked = {"api_key", "token", "password", "secret", "access_token", "refresh_token"}
        clean: dict[str, Any] = {}
        for key, value in (context or {}).items():
            if any(part in str(key).lower() for part in blocked):
                continue
            clean[key] = self._truncate(value)
        return clean

    def _truncate(self, value: Any, max_items: int = 100) -> Any:
        if isinstance(value, dict):
            return {k: self._truncate(v, max_items=max_items) for k, v in list(value.items())[:max_items]}
        if isinstance(value, list):
            return [self._truncate(v, max_items=max_items) for v in value[:max_items]]
        if isinstance(value, str):
            return value[:4000]
        return value

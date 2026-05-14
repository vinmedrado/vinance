from __future__ import annotations

from typing import Any

from backend.app.intelligence.financial_safety_service import FinancialSafetyService
from backend.app.intelligence.humanization_engine import HumanizationEngine

class ConversationalFinancialAdvisor:
    """Advisor conversacional determinístico baseado nos dados reais do ERP/contexto."""

    @staticmethod
    def _money(value: float) -> str:
        return f"R$ {float(value or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @classmethod
    def answer(cls, question: str, context: dict[str, Any], learning_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        q = (question or "").strip().lower()
        learning_profile = learning_profile or context.get("learning_profile", {}) or {}
        tone = learning_profile.get("preferred_tone", "consultive")
        detail = learning_profile.get("preferred_detail_level", "short")
        summary = context.get("current_financial_situation", {}) or {}
        health = context.get("health", {}) or {}
        budget = context.get("budget_advisor", {}) or {}
        goals = context.get("dynamic_goals", {}).get("goals", []) or context.get("goals", []) or []
        forecast = context.get("forecast", {}) or {}
        memory = context.get("memory", {}) or {}
        behavior = context.get("behavior", {}) or {}
        capacity = float(context.get("investment_capacity", 0) or 0)
        intent = "general_guidance"
        cards: list[dict[str, Any]] = []
        quick_actions = ["Revisar orçamento", "Cadastrar despesa", "Ver metas", "Ver investimentos"]
        if any(w in q for w in ("quanto posso investir", "posso investir", "aporte", "investir este mês")):
            intent = "investment_capacity"
            if capacity <= 0 or health.get("financial_phase") in ("sobrevivência", "recuperação"):
                answer = "Neste mês, o mais seguro é priorizar organização financeira, contas e reserva antes de aumentar investimentos."
            else:
                answer = f"Você tem margem segura estimada de {cls._money(capacity)} para investir neste mês, mantendo uma proteção básica no orçamento."
            cards.append({"label": "Sobra segura", "value": cls._money(capacity)})
        elif any(w in q for w in ("quitar", "dívida", "divida", "investir")):
            intent = "debt_vs_invest"
            decision = context.get("decision_advisor", {})
            answer = decision.get("recommendation") or "Se há dívida cara ou atraso, o caminho mais seguro é reduzir essa pressão antes de aumentar investimentos."
            cards.append({"label": "Dívidas/renda", "value": f"{float(summary.get('debt_ratio',0))*100:.0f}%"})
        elif any(w in q for w in ("modelo mudou", "por que meu modelo", "modelo financeiro")):
            intent = "budget_model_explanation"
            answer = f"Seu modelo recomendado é {budget.get('model_label', budget.get('recommended_model','o modelo atual'))} porque sua renda, despesas, dívidas e reserva indicam essa fase financeira. {budget.get('reason','')}"
            cards.append({"label": "Modelo", "value": budget.get("model_label", budget.get("recommended_model"))})
        elif any(w in q for w in ("melhorando", "evolução", "evolucao", "estou melhor")):
            intent = "financial_evolution"
            answer = f"Seu score financeiro está em {health.get('health_score',0)}/100 e a tendência recente aparece como {memory.get('trend', health.get('evolution_trend','estável'))}. {memory.get('insights',[None])[0] if memory.get('insights') else ''}"
            cards.append({"label": "Score financeiro", "value": f"{health.get('health_score',0)}/100"})
        elif any(w in q for w in ("quanto falta", "meta", "objetivo")):
            intent = "goal_progress"
            if goals:
                g = goals[0]
                target = float(g.get("target_amount", 0) or 0)
                current = float(g.get("current_amount", 0) or 0)
                missing = max(0, target-current)
                answer = f"Para sua meta principal, faltam aproximadamente {cls._money(missing)}. Com o aporte atual, o Vinance recalcula prazo e chance de sucesso conforme sua realidade muda."
                cards.append({"label": "Falta para meta", "value": cls._money(missing)})
            else:
                answer = "Ainda não encontrei uma meta ativa. Cadastre uma meta para eu calcular quanto falta, prazo e aporte ideal."
        elif any(w in q for w in ("categoria", "controlar", "gasto", "despesa")):
            intent = "category_control"
            cats = memory.get("critical_categories", [])
            if cats:
                answer = f"A categoria que mais merece atenção agora é {cats[0].get('category')}. Controlar esse ponto tende a liberar margem sem mudar toda sua rotina."
                cards.append({"label": "Categoria crítica", "value": cats[0].get("category")})
            else:
                answer = "Pelos dados atuais, ainda não há categoria crítica clara. Continue categorizando despesas para eu identificar padrões com mais precisão."
        elif any(w in q for w in ("carteira", "perfil", "compatível", "compativel")):
            intent = "portfolio_fit"
            risk = context.get("profile", {}).get("risk_profile") or "moderado"
            answer = f"Sua carteira deve respeitar seu perfil {risk} e sua fase financeira atual. Se a saúde financeira estiver apertada, o Vinance prioriza reserva e caixa antes de sugerir mais risco."
        else:
            next_steps = context.get("next_steps", [])
            answer = context.get("decision_advisor", {}).get("recommendation") or (next_steps[0] if next_steps else "O melhor próximo passo é manter renda, despesas e metas atualizadas para eu orientar sua evolução com precisão.")
        human = HumanizationEngine.refine(answer, phase=health.get("financial_phase"), tone=tone, detail_level=detail)
        response = {
            "intent": intent,
            "answer": human,
            "used_real_data": True,
            "confidence": float(budget.get("confidence_score", 0.75) or 0.75),
            "recommended_action": context.get("next_steps", ["Atualizar orçamento"])[0] if context.get("next_steps") else "Atualizar orçamento",
            "context_cards": cards,
            "quick_actions": quick_actions,
        }
        return FinancialSafetyService.evaluate(response, context)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from backend.app.intelligence.contextual_financial_memory import ContextualFinancialMemory
from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails
from backend.app.intelligence.humanization_engine import HumanizationEngine
from backend.app.intelligence.ai_analytics_service import AIAnalyticsService
from backend.app.intelligence.advisor_performance_service import AdvisorPerformanceService
from backend.app.intelligence.conversational_memory_service import ConversationalMemoryService
from backend.app.intelligence.financial_rag_engine import FinancialRAGEngine
from backend.app.intelligence.premium_advisor_mode import PremiumAdvisorMode


@dataclass(frozen=True)
class AdvisorIntent:
    name: str
    confidence: float
    entities: dict[str, Any]


class FinancialAIOrchestrator:
    """Cérebro do advisor financeiro.

    Não usa FAQ nem árvore fixa. Ele interpreta a pergunta por intenção semântica leve,
    monta contexto consolidado, aplica memória, personalização e guardrails, e gera
    uma resposta consultiva com dados reais do ERP.
    """

    @staticmethod
    def _money(value: float | int | None) -> str:
        return f"R$ {float(value or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @staticmethod
    def _pct(value: float | int | None) -> str:
        return f"{float(value or 0) * 100:.0f}%"

    @classmethod
    def detect_intent(cls, question: str) -> AdvisorIntent:
        q = (question or "").lower()
        groups = {
            "investment_capacity": ["quanto posso investir", "posso investir", "aporte", "investir este mês", "investir esse mês"],
            "debt_vs_invest": ["quitar", "dívida", "divida", "investir ou", "vale investir"],
            "financial_health": ["estou melhorando", "melhorando", "saudável", "saudavel", "minha situação", "evolução", "evolucao"],
            "goal_planning": ["meta", "objetivo", "quanto falta", "consigo", "viajar", "carro", "imóvel", "imovel", "aposentadoria"],
            "spending_control": ["gastando demais", "gasto", "despesa", "categoria", "controlar", "orçamento", "orcamento"],
            "portfolio_risk": ["carteira", "arriscada", "risco", "perfil", "cripto", "ações", "acoes", "fiis", "etfs"],
            "budget_model": ["modelo", "50/30/20", "70/20/10", "base zero", "mudou"],
            "next_step": ["próximo passo", "proximo passo", "priorizar", "o que fazer", "maior problema"],
        }
        hits: list[tuple[str, int]] = []
        for name, words in groups.items():
            score = sum(1 for w in words if w in q)
            if score:
                hits.append((name, score))
        if not hits:
            return AdvisorIntent("open_financial_guidance", 0.58, {})
        hits.sort(key=lambda x: x[1], reverse=True)
        return AdvisorIntent(hits[0][0], min(0.95, 0.60 + hits[0][1] * 0.12), {})

    @classmethod
    def build_prompt_context(cls, context: dict[str, Any], memory: dict[str, Any], learning: dict[str, Any]) -> dict[str, Any]:
        situation = context.get("current_financial_situation", {}) or {}
        health = context.get("health", {}) or {}
        return {
            "financial_snapshot": {
                "income": situation.get("monthly_income", 0),
                "expenses": situation.get("total_expenses", 0),
                "expense_ratio": situation.get("expense_ratio", 0),
                "debt_ratio": situation.get("debt_ratio", 0),
                "investment_capacity": context.get("investment_capacity", 0),
                "recommended_model": context.get("recommended_model"),
                "health_score": health.get("health_score"),
                "financial_phase": health.get("financial_phase"),
            },
            "memory": memory,
            "learning_profile": learning,
            "alerts": context.get("alerts", [])[:5],
            "next_steps": context.get("next_steps", [])[:5],
        }

    @classmethod
    def _answer_for_intent(cls, intent: AdvisorIntent, question: str, context: dict[str, Any], memory: dict[str, Any], learning: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
        situation = context.get("current_financial_situation", {}) or {}
        health = context.get("health", {}) or {}
        budget = context.get("budget_advisor", {}) or {}
        behavior = context.get("behavior", {}) or {}
        goals = context.get("dynamic_goals", {}).get("goals", []) or context.get("goals", []) or []
        forecast = context.get("forecast", {}) or {}
        capacity = float(context.get("investment_capacity", 0) or 0)
        cards: list[dict[str, Any]] = []
        action = context.get("next_steps", ["Atualizar orçamento"])[0] if context.get("next_steps") else "Atualizar orçamento"
        phase = health.get("financial_phase", "em análise")
        model = budget.get("model_label") or budget.get("recommended_model") or context.get("recommended_model") or "modelo em análise"
        expense_ratio = float(situation.get("expense_ratio", 0) or 0)
        debt_ratio = float(situation.get("debt_ratio", 0) or 0)
        reserve_months = float((health.get("metrics", {}) or {}).get("reserve_months", 0) or 0)

        if intent.name == "investment_capacity":
            cards.append({"label": "Sobra segura", "value": cls._money(capacity)})
            cards.append({"label": "Fase", "value": phase})
            if capacity <= 0 or phase in {"sobrevivência", "recuperação"}:
                answer = "Hoje eu não aumentaria investimento. Seu foco deve ser proteger o caixa, organizar contas e criar uma margem mínima antes de assumir mais risco."
                action = "Revisar orçamento e priorizar reserva/dívidas"
            else:
                answer = f"Com os dados atuais, sua margem segura estimada para este mês é {cls._money(capacity)}. Eu manteria esse valor como teto inicial e só aumentaria depois de confirmar que as despesas do mês ficaram dentro do plano."
                action = "Separar aporte seguro e acompanhar despesas da semana"
        elif intent.name == "debt_vs_invest":
            cards.append({"label": "Dívidas/renda", "value": cls._pct(debt_ratio)})
            cards.append({"label": "Reserva", "value": f"{reserve_months:.1f} meses"})
            if debt_ratio >= 0.15 or situation.get("overdue_bills", 0):
                answer = "Pelo seu contexto, quitar ou renegociar dívidas vem antes de aumentar investimentos. Isso reduz pressão mensal e melhora sua capacidade de aporte nos próximos meses."
                action = "Priorizar dívidas e contas atrasadas"
            elif reserve_months < 3:
                answer = "Você pode investir pouco, mas a prioridade ainda é formar reserva. A melhor decisão é dividir a sobra com foco maior em caixa/reserva antes de buscar rentabilidade."
                action = "Fortalecer reserva de emergência"
            else:
                answer = "Como a dívida não parece dominar seu orçamento e existe alguma estabilidade, faz sentido avaliar um aporte moderado, sem comprometer reserva e contas essenciais."
                action = "Investir de forma moderada mantendo reserva"
        elif intent.name == "financial_health":
            cards.append({"label": "Score", "value": f"{health.get('health_score', 0)}/100"})
            cards.append({"label": "Tendência", "value": memory.get("trend", health.get("evolution_trend", "estável"))})
            answer = f"Sua fase atual é {phase} e seu score está em {health.get('health_score', 0)}/100. O principal sinal que observo é: {', '.join(memory.get('recurring_patterns', [])[:2]) or 'acompanhar consistência por mais alguns ciclos'}."
            action = memory.get("priority_now", "manter orçamento atualizado")
        elif intent.name == "goal_planning":
            if goals:
                g = goals[0]
                target = float(g.get("target_amount", 0) or 0)
                current = float(g.get("current_amount", 0) or 0)
                missing = max(0, target - current)
                prob = float(g.get("success_probability", 0) or 0)
                cards.append({"label": "Falta para meta", "value": cls._money(missing)})
                cards.append({"label": "Chance estimada", "value": f"{prob:.0f}%"})
                answer = f"Para sua meta principal, faltam cerca de {cls._money(missing)}. Com sua capacidade atual de {cls._money(capacity)}/mês, eu acompanharia prazo e aporte antes de assumir novos compromissos grandes."
                if capacity <= 0:
                    answer += " Neste momento, a meta depende mais de reorganização do orçamento do que de investimento."
                action = "Revisar aporte e prazo da meta"
            else:
                answer = "Ainda não encontrei uma meta ativa. Para responder com precisão, cadastre valor, prazo e prioridade; depois eu calculo aporte necessário, atraso e cenário provável."
                action = "Cadastrar meta financeira"
        elif intent.name == "spending_control":
            cats = memory.get("critical_categories", []) or []
            cards.append({"label": "Despesas/renda", "value": cls._pct(expense_ratio)})
            if cats:
                answer = f"O ponto que mais merece atenção agora é {cats[0].get('category')}. Controlar essa categoria tende a liberar margem sem exigir uma mudança completa no seu padrão de vida."
                cards.append({"label": "Categoria crítica", "value": cats[0].get("category")})
                action = f"Definir limite semanal para {cats[0].get('category')}"
            elif expense_ratio >= 0.70:
                answer = "Suas despesas estão ocupando uma parte relevante da renda. Eu começaria revisando gastos variáveis e assinaturas antes de mexer em itens essenciais."
                action = "Revisar gastos variáveis"
            else:
                answer = "Seu orçamento não mostra um excesso crítico pelos dados atuais. O foco deve ser manter consistência e transformar a sobra em reserva, meta ou aporte planejado."
                action = "Manter limites e automatizar aporte"
        elif intent.name == "portfolio_risk":
            risk_behavior = behavior.get("risk_behavior_score", 50)
            cards.append({"label": "Risco comportamental", "value": f"{risk_behavior}/100"})
            cards.append({"label": "Fase", "value": phase})
            if phase in {"sobrevivência", "recuperação"}:
                answer = "Antes de avaliar uma carteira mais arriscada, eu priorizaria caixa, dívidas e reserva. Uma carteira incompatível com sua fase pode piorar sua estabilidade."
                action = "Reduzir risco e fortalecer reserva"
            else:
                answer = "A carteira deve respeitar sua fase, reserva e tolerância real a oscilações. Eu manteria diversificação e evitaria concentração alta em ativos voláteis."
                action = "Revisar alocação e concentração"
        elif intent.name == "budget_model":
            cards.append({"label": "Modelo", "value": model})
            cards.append({"label": "Confiança", "value": f"{float(budget.get('confidence_score', 0.75))*100:.0f}%"})
            answer = f"O modelo recomendado é {model} porque suas despesas, dívidas, reserva e sobra indicam a fase de {phase}. {budget.get('reason', '')}".strip()
            action = "Aplicar limites sugeridos neste mês"
        elif intent.name == "next_step":
            problem = "despesas" if expense_ratio >= 0.70 else "reserva" if reserve_months < 3 else "consistência de aporte"
            cards.append({"label": "Prioridade", "value": problem})
            answer = f"Seu próximo passo mais importante é trabalhar {problem}. Isso é o que mais pode melhorar sua estabilidade e liberar espaço para metas e investimentos depois."
            action = f"Focar em {problem} por 30 dias"
        else:
            cards.append({"label": "Score", "value": f"{health.get('health_score', 0)}/100"})
            cards.append({"label": "Modelo", "value": model})
            answer = f"Pelo seu contexto atual, você está na fase de {phase}. Eu analisaria primeiro renda, despesas, dívidas e reserva; depois conectaria isso às metas e investimentos. A prioridade agora é {memory.get('priority_now', 'manter clareza do orçamento')}."
            action = memory.get("priority_now", "Atualizar orçamento")
        return answer, cards, action

    @classmethod
    def answer(cls, question: str, context: dict[str, Any], learning_profile: dict[str, Any] | None = None) -> dict[str, Any]:
        started = AIAnalyticsService.start_timer()
        learning_profile = learning_profile or context.get("learning_profile", {}) or {}
        context = AdvisorPerformanceService.compact_context(context)
        org_id = str(context.get("organization_id", "default-org"))
        user_id = str(context.get("user_id", "default-user"))

        conversation_memory = ConversationalMemoryService.get_summary(organization_id=org_id, user_id=user_id)
        memory = ContextualFinancialMemory.summarize({**context, "conversation_memory": conversation_memory})
        rag_items = FinancialRAGEngine.retrieve(question, context, conversation_memory, top_k=6)
        intent = cls.detect_intent(question)
        safety_request = FinancialSafetyGuardrails.inspect_request(question, context)
        raw_answer, cards, action = cls._answer_for_intent(intent, question, context, memory, learning_profile)

        # O RAG local não substitui cálculo financeiro; ele adiciona continuidade e contexto relevante.
        if rag_items and intent.name == "open_financial_guidance":
            top = rag_items[0]
            raw_answer += f" Pelo contexto mais relevante que encontrei ({top.get('title')}), eu começaria por esse ponto antes de abrir novas frentes."

        if safety_request.get("must_prioritize_cash"):
            raw_answer = "Pelo seu momento financeiro, eu priorizaria caixa, contas e reserva antes de aumentar risco. Investir mais agora pode apertar o orçamento e atrasar sua recuperação."
            action = "Organizar caixa e reserva antes de investir"
        detail = learning_profile.get("preferred_detail_level", "short")
        tone = learning_profile.get("preferred_tone", "consultive")
        phase = (context.get("health") or {}).get("financial_phase")
        human = HumanizationEngine.refine(raw_answer, phase=phase, tone=tone, detail_level=detail)
        response = {
            "intent": intent.name,
            "answer": human,
            "used_real_data": True,
            "confidence": intent.confidence,
            "recommended_action": action,
            "context_cards": cards,
            "quick_actions": cls.suggest_questions(context, memory),
            "prompt_context": cls.build_prompt_context(context, memory, learning_profile),
            "memory_used": memory,
            "conversation_memory": conversation_memory,
            "rag_context": [{"kind": i.get("kind"), "title": i.get("title"), "score": i.get("relevance_score")} for i in rag_items],
            "provider": context.get("llm_provider", "local_fallback"),
        }
        response = FinancialSafetyGuardrails.apply(response, context)
        response = PremiumAdvisorMode.build(response, context)
        ConversationalMemoryService.add_turn(organization_id=org_id, user_id=user_id, question=question, answer=response.get("answer", ""), intent=intent.name)
        response["ai_analytics"] = AIAnalyticsService.record_usage(
            organization_id=org_id, user_id=user_id, question=question, intent=intent.name,
            provider=response.get("provider", "local_fallback"), success=True, started_at=started,
        )
        return response

    @classmethod
    def answer_from_db(cls, db: Any, ctx: Any, question: str, *, year: int | None = None, month: int | None = None) -> dict[str, Any]:
        from backend.app.intelligence.financial_context_builder import FinancialContextBuilder
        cache_key = AdvisorPerformanceService.cache_key(ctx.organization_id, ctx.user_id, year, month)
        context = AdvisorPerformanceService.get_cached_context(cache_key)
        if context is None:
            context = FinancialContextBuilder.build(db, ctx, year=year, month=month)
            AdvisorPerformanceService.set_cached_context(cache_key, context)
        from backend.app.intelligence.user_learning_profile_service import UserLearningProfileService
        learning = UserLearningProfileService.update_from_interaction(db, organization_id=ctx.organization_id, user_id=ctx.user_id, question=question, context=context)
        return cls.answer(question, context, learning)

    @classmethod
    def suggest_questions(cls, context: dict[str, Any], memory: dict[str, Any] | None = None) -> list[str]:
        memory = memory or ContextualFinancialMemory.summarize(context)
        phase = str((context.get("health") or {}).get("financial_phase", "")).lower()
        questions = [
            "Qual meu próximo passo financeiro?",
            "Quanto posso investir este mês?",
            "Estou melhorando financeiramente?",
        ]
        if phase in {"sobrevivência", "recuperação"}:
            questions.insert(1, "Vale quitar dívida ou investir?")
        if memory.get("critical_categories"):
            questions.append("Qual categoria preciso controlar?")
        if context.get("goals") or context.get("dynamic_goals", {}).get("goals"):
            questions.append("Quanto falta para minha meta?")
        questions.append("Meu orçamento está saudável?")
        return list(dict.fromkeys(questions))[:6]

from backend.app.intelligence.ai_analytics_service import AIAnalyticsService
from backend.app.intelligence.conversational_memory_service import ConversationalMemoryService
from backend.app.intelligence.financial_ai_orchestrator import FinancialAIOrchestrator
from backend.app.intelligence.financial_rag_engine import FinancialRAGEngine
from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails
from backend.app.intelligence.premium_advisor_mode import PremiumAdvisorMode


def ctx(org="org-a", user="u1"):
    return {
        "organization_id": org,
        "user_id": user,
        "investment_capacity": 700,
        "current_financial_situation": {
            "monthly_income": 6000,
            "total_expenses": 3900,
            "expense_ratio": 0.65,
            "debt_ratio": 0.04,
            "emergency_reserve": 9000,
            "overdue_bills": 0,
        },
        "budget_advisor": {"recommended_model": "50_30_20", "model_label": "50/30/20", "reason": "há equilíbrio para investir com prudência", "confidence_score": 0.86},
        "recommended_model": "50_30_20",
        "health": {"health_score": 78, "financial_phase": "crescimento", "risk_level": "baixo", "metrics": {"reserve_months": 3.2}},
        "memory": {"trend": "melhorando", "patterns": ["sobra recorrente"], "critical_categories": [{"category": "lazer", "total": 820}]},
        "behavior": {"behavioral_score": 80, "discipline_score": 82, "stability_score": 76, "risk_behavior_score": 25},
        "goals": [{"goal_type": "viagem", "target_amount": 12000, "current_amount": 5000, "success_probability": 72}],
        "forecast": {"scenarios": [{"name": "base", "projected_net_worth": 25000}]},
        "alerts": ["Gasto de lazer acima do padrão"],
        "next_steps": ["Separar aporte no início do mês"],
        "learning_profile": {"preferred_tone": "consultive", "preferred_detail_level": "short"},
    }


def test_conversational_memory_is_isolated_by_tenant():
    ConversationalMemoryService.add_turn(organization_id="org-a", user_id="u1", question="posso investir?", answer="Sim, com limite seguro", intent="investment_capacity")
    a = ConversationalMemoryService.get_summary(organization_id="org-a", user_id="u1")
    b = ConversationalMemoryService.get_summary(organization_id="org-b", user_id="u1")
    assert a["turns"] == 1
    assert b["turns"] == 0
    assert a["memory_hash"] != b["memory_hash"]


def test_financial_rag_retrieves_relevant_context():
    items = FinancialRAGEngine.retrieve("qual categoria preciso controlar?", ctx())
    assert items
    assert all(i["organization_id"] == "org-a" for i in items)
    assert any(i["kind"] in {"memory", "snapshot", "alert"} for i in items)


def test_premium_advisor_adds_strategic_structure():
    response = {"answer": "Você pode manter aporte moderado.", "recommended_action": "Aportar dentro da margem segura", "safety_warnings": []}
    out = PremiumAdvisorMode.build(response, ctx())
    assert "premium_advisor" in out
    assert "alternatives" in out["premium_advisor"]
    assert "disclaimer" in out


def test_orchestrator_returns_memory_rag_and_analytics():
    out = FinancialAIOrchestrator.answer("quanto posso investir este mês e qual risco?", ctx())
    assert out["used_real_data"] is True
    assert out["conversation_memory"]
    assert isinstance(out["rag_context"], list)
    assert out["ai_analytics"]["success"] is True
    assert out["premium_advisor"]["diagnosis"]


def test_safety_blocks_aggressive_investment_when_critical():
    critical = ctx()
    critical["investment_capacity"] = 0
    critical["health"] = {"health_score": 25, "financial_phase": "recuperação", "risk_level": "crítico", "metrics": {"reserve_months": 0.2}}
    out = FinancialAIOrchestrator.answer("posso colocar tudo em cripto?", critical)
    assert "reserva" in out["answer"].lower() or "caixa" in out["answer"].lower()
    assert "educacionais" in out["disclaimer"]


def test_ai_analytics_does_not_store_raw_question():
    start = AIAnalyticsService.start_timer()
    event = AIAnalyticsService.record_usage(organization_id="org-a", user_id="u1", question="minha dívida está ruim?", intent="debt_vs_invest", provider="local_fallback", success=True, started_at=start)
    assert event["question_hash"] != "minha dívida está ruim?"
    report = AIAnalyticsService.report(organization_id="org-a", user_id="u1")
    assert report["total_interactions"] >= 1

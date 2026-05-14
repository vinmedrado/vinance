from backend.app.intelligence.financial_ai_orchestrator import FinancialAIOrchestrator
from backend.app.intelligence.contextual_financial_memory import ContextualFinancialMemory
from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails
from backend.app.intelligence.continuous_financial_copilot import ContinuousFinancialCopilot


def ctx(org="org-a", user="u1"):
    return {
        "organization_id": org,
        "user_id": user,
        "investment_capacity": 650,
        "current_financial_situation": {
            "monthly_income": 5200,
            "total_expenses": 3650,
            "expense_ratio": 0.70,
            "debt_ratio": 0.06,
            "emergency_reserve": 7000,
            "overdue_bills": 0,
        },
        "budget_advisor": {"recommended_model": "50_30_20", "model_label": "50/30/20", "reason": "há equilíbrio entre despesas, reserva e sobra.", "confidence_score": 0.84, "investment_capacity": 650},
        "health": {"health_score": 72, "risk_level": "moderado", "financial_phase": "crescimento", "evolution_trend": "melhorando", "metrics": {"reserve_months": 3.1}},
        "memory": {"memory_strength": "boa", "trend": "melhorando", "patterns": ["sobra recorrente"], "insights": ["Sua margem melhorou recentemente."], "critical_categories": [{"category": "lazer", "total": 820}]},
        "behavior": {"behavioral_score": 74, "discipline_score": 77, "stability_score": 70, "risk_behavior_score": 32, "signals": ["consistência de aporte"]},
        "dynamic_goals": {"goals": [{"goal_type": "viagem", "target_amount": 10000, "current_amount": 3200, "success_probability": 68}]},
        "goals": [{"goal_type": "viagem", "target_amount": 10000, "current_amount": 3200, "success_probability": 68}],
        "forecast": {"scenarios": [{"name": "base", "projected_net_worth": 18000}]},
        "next_steps": ["Separar aporte no início do mês."],
        "learning_profile": {"preferred_tone": "consultive", "preferred_detail_level": "short", "financial_literacy_level": "beginner"},
    }


def test_orchestrator_answers_free_question_with_real_context():
    out = FinancialAIOrchestrator.answer("consigo viajar sem atrapalhar minha meta?", ctx())
    assert out["used_real_data"] is True
    assert out["intent"] == "goal_planning"
    assert out["context_cards"]
    assert "disclaimer" in out


def test_contextual_memory_influences_suggestions():
    memory = ContextualFinancialMemory.summarize(ctx())
    assert "lazer" in str(memory.get("critical_categories", [])).lower()
    suggestions = FinancialAIOrchestrator.suggest_questions(ctx(), memory)
    assert any("categoria" in q.lower() for q in suggestions)


def test_guardrails_block_irresponsible_promise():
    critical = ctx()
    critical["investment_capacity"] = 0
    critical["health"] = {"health_score": 25, "risk_level": "crítico", "financial_phase": "recuperação", "metrics": {"reserve_months": 0}}
    out = FinancialSafetyGuardrails.apply({"answer": "Compre cripto porque retorno garantido e sem risco.", "recommended_action": "comprar"}, critical)
    assert "garantido" not in out["answer"].lower()
    assert out["safety_warnings"]
    assert "educacionais" in out["disclaimer"]


def test_orchestrator_adapts_when_financially_critical():
    critical = ctx()
    critical["investment_capacity"] = 0
    critical["health"] = {"health_score": 28, "risk_level": "crítico", "financial_phase": "recuperação", "metrics": {"reserve_months": 0.2}}
    out = FinancialAIOrchestrator.answer("minha carteira está arriscada? posso colocar mais cripto?", critical)
    assert "caixa" in out["answer"].lower() or "reserva" in out["answer"].lower()
    assert out["intent"] == "portfolio_risk"


def test_copilot_keeps_tenant_metadata_indirectly_in_context():
    a = ctx("org-a", "u1")
    b = ctx("org-b", "u2")
    assert a["organization_id"] != b["organization_id"]
    events = ContinuousFinancialCopilot.monitor(a)
    assert isinstance(events, list)

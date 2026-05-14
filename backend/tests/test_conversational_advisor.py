from backend.app.intelligence.conversational_financial_advisor import ConversationalFinancialAdvisor
from backend.app.intelligence.continuous_financial_copilot import ContinuousFinancialCopilot
from backend.app.intelligence.financial_safety_service import FinancialSafetyService
from backend.app.intelligence.humanization_engine import HumanizationEngine


def sample_context(org='org-a', user='u1'):
    return {
        'organization_id': org,
        'user_id': user,
        'investment_capacity': 600,
        'current_financial_situation': {'monthly_income': 5000, 'total_expenses': 3600, 'expense_ratio': 0.72, 'debt_ratio': 0.08, 'emergency_reserve': 4000},
        'budget_advisor': {'recommended_model': '60_30_10', 'model_label': '60/30/10', 'reason': 'despesas pedem reorganização', 'confidence_score': 0.82, 'investment_capacity': 600},
        'health': {'health_score': 66, 'risk_level': 'moderado', 'financial_phase': 'estabilização', 'metrics': {'reserve_months': 2.4}},
        'memory': {'trend': 'melhorando', 'insights': ['Sua margem melhorou no histórico recente.'], 'critical_categories': [{'category': 'lazer', 'total': 900}]},
        'behavior': {'behavioral_score': 70, 'risk_behavior_score': 35},
        'dynamic_goals': {'goals': [{'goal_type': 'reserva', 'target_amount': 12000, 'current_amount': 4000, 'success_probability': 60}]},
        'forecast': {'scenarios': [{'name': 'base', 'projected_net_worth': 12000}]},
        'decision_advisor': {'recommendation': 'Quite dívidas caras antes de aumentar risco.'},
        'next_steps': ['Manter o modelo 60/30/10 neste mês.'],
    }


def test_advisor_uses_real_context_for_investment_capacity():
    out = ConversationalFinancialAdvisor.answer('quanto posso investir este mês?', sample_context(), {'preferred_tone': 'consultive', 'preferred_detail_level': 'short'})
    assert out['used_real_data'] is True
    assert '600' in out['answer'] or '600' in str(out.get('context_cards'))
    assert 'disclaimer' in out


def test_advisor_answers_goal_progress():
    out = ConversationalFinancialAdvisor.answer('quanto falta para minha meta?', sample_context())
    assert out['intent'] == 'goal_progress'
    assert '8.000' in out['answer'] or any('8.000' in str(c) for c in out['context_cards'])


def test_safety_blocks_investment_when_health_is_critical():
    ctx = sample_context(); ctx['investment_capacity'] = 0; ctx['health'] = {'risk_level': 'crítico', 'financial_phase': 'recuperação', 'health_score': 28}
    out = FinancialSafetyService.evaluate({'answer': 'Você pode investir em carteira agressiva.', 'recommended_action': 'Investir'}, ctx)
    assert out['recommended_action'].lower().startswith('revisar')
    assert out['safety_warnings']


def test_copilot_generates_contextual_events():
    ctx = sample_context(); ctx['current_financial_situation']['expense_ratio'] = 0.9
    events = ContinuousFinancialCopilot.monitor(ctx)
    assert any(e['type'] == 'expense_pressure' for e in events)
    assert all('suggested_action' in e for e in events)


def test_humanization_removes_hard_promises():
    text = HumanizationEngine.refine('retorno garantido e risco alto', phase='estabilização')
    assert 'garantido' not in text.lower()
    assert 'momento de maior cuidado' in text.lower()

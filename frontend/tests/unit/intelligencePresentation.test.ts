import { describe, expect, test } from 'vitest';
import {
  describeAdvisorContext,
  presentAdvisorWarning,
  presentIntelligenceWarning,
  riskProfileLabel,
} from '../../src/features/intelligence/utils/presentation';

describe('apresentação da inteligência', () => {
  test('substitui códigos internos por explicações para pessoas', () => {
    expect(presentIntelligenceWarning('UNSAFE_DATA_QUALITY')).toContain('qualidade');
    expect(presentIntelligenceWarning('DECISION_CORE_MISSING')).toContain('informações essenciais');
    expect(presentIntelligenceWarning('UNKNOWN_INTERNAL_CODE')).not.toContain('UNKNOWN_INTERNAL_CODE');
  });

  test('traduz perfil e avisos do assistente sem inventar confiança', () => {
    expect(riskProfileLabel('CONSERVATIVE')).toBe('Conservador');
    expect(presentAdvisorWarning({ code: 'groq_unavailable', message: 'provider error' })).toContain('temporariamente indisponível');
    expect(presentAdvisorWarning({ code: 'context_warning', message: 'INVESTMENT_CAPACITY_UNKNOWN' })).toContain('capacidade segura');
    expect(presentAdvisorWarning({ code: 'context_warning', message: 'Perfil financeiro ainda não cadastrado; contexto financeiro limitado.' })).toBe('Perfil financeiro ainda não cadastrado; contexto financeiro limitado.');
    expect(presentAdvisorWarning({ code: 'context_warning', message: 'Contexto financeiro/mercado indisponível: timeout interno' })).toBe('Parte do contexto financeiro ou de mercado está temporariamente indisponível.');
  });

  test('descreve apenas o contexto confirmado pela API', () => {
    expect(describeAdvisorContext({ financial: true, market: false, memory: true })).toEqual([
      'Situação financeira considerada',
      'Contexto recente da conversa considerado',
    ]);
    expect(describeAdvisorContext({ financial: false, market: false, memory: false })).toEqual(['Resposta com contexto limitado']);
  });
});

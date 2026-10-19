import type { AdvisorContextUsed, AdvisorWarning } from '../../advisor/types/advisor.types';

const intelligenceMessages: Record<string, string> = {
  UNSAFE_DATA_QUALITY: 'Os dados disponíveis ainda não têm qualidade suficiente para uma decisão segura.',
  CONFIDENCE_BELOW_POLICY_MINIMUM: 'A confiança da análise está abaixo do mínimo exigido pela política financeira.',
  DECISION_CORE_MISSING: 'Faltam informações essenciais para concluir esta análise.',
  INVESTMENT_CAPACITY_UNKNOWN: 'A capacidade segura de investimento ainda não pôde ser calculada.',
};

const advisorMessages: Record<string, string> = {
  prompt_injection_blocked: 'Esse pedido não pode ser atendido com segurança pelo assistente.',
  context_limited: 'O assistente recebeu contexto financeiro incompleto. Complete seus dados para uma resposta mais precisa.',
  groq_unavailable: 'O serviço de linguagem está temporariamente indisponível. Nenhuma resposta foi inventada.',
};

function normalize(value: string) {
  return value.trim().replace(/[.:;,]+$/, '');
}

export function presentIntelligenceWarning(value: string) {
  const key = normalize(value).toUpperCase();
  if (intelligenceMessages[key]) return intelligenceMessages[key];
  if (/^[A-Z0-9_]+$/.test(key)) return 'Existe uma restrição técnica que impede uma análise completa neste momento.';
  return value;
}

export function presentAdvisorWarning(warning: AdvisorWarning) {
  if (warning.code === 'context_warning') {
    const message = warning.message.trim();
    if (/^contexto financeiro\/mercado indisponível:/i.test(message)) {
      return 'Parte do contexto financeiro ou de mercado está temporariamente indisponível.';
    }
    return message
      ? presentIntelligenceWarning(message)
      : 'Parte do contexto necessário para esta resposta não está disponível.';
  }
  return advisorMessages[warning.code] ?? presentIntelligenceWarning(warning.message);
}

export function describeAdvisorContext(context: AdvisorContextUsed | undefined) {
  if (!context) return [];
  const descriptions: string[] = [];
  if (context.financial) descriptions.push('Situação financeira considerada');
  if (context.market) descriptions.push('Dados de mercado considerados');
  if (context.memory) descriptions.push('Contexto recente da conversa considerado');
  if (descriptions.length === 0) descriptions.push('Resposta com contexto limitado');
  return descriptions;
}

export function riskProfileLabel(value: string | null | undefined) {
  const key = String(value ?? '').trim().toUpperCase();
  return ({
    CONSERVATIVE: 'Conservador',
    MODERATE: 'Moderado',
    AGGRESSIVE: 'Agressivo',
    CONSERVADOR: 'Conservador',
    MODERADO: 'Moderado',
    AGRESSIVO: 'Agressivo',
  } as Record<string, string>)[key] ?? (value || 'Não definido');
}

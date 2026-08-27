import { afterEach, describe, expect, test, vi } from 'vitest';
import { getInvestmentWorkspaceRecommendation } from '../../src/features/investment-workspace/services/investmentWorkspace.service';
import { api } from '../../src/services/api';
import { completeBudgetResponse } from '../fixtures/investmentFixtures';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

afterEach(() => vi.restoreAllMocks());

describe('rastreabilidade no transporte do Budget Advisor', () => {
  test('envia IDs válidos, explain=true e preserva os mesmos IDs na resposta', async () => {
    const captured: Array<Record<string, string>> = [];
    vi.spyOn(api, 'get').mockImplementation(async (_url, config) => {
      const headers = config?.headers as Record<string, string>;
      captured.push(headers);
      return {
        data: {
          ...completeBudgetResponse,
          decision_id: headers['X-Decision-ID'],
          correlation_id: headers['X-Correlation-ID'],
        },
        headers: {},
      } as never;
    });

    const filters = { budget: 300, market: 'FII', profile: 'CONSERVATIVE' as const, includeWarnings: false };
    const first = await getInvestmentWorkspaceRecommendation(filters);
    const second = await getInvestmentWorkspaceRecommendation(filters);

    expect(captured[0]['X-Decision-ID']).toMatch(uuidPattern);
    expect(captured[0]['X-Correlation-ID']).toMatch(uuidPattern);
    expect(first.decision_id).toBe(captured[0]['X-Decision-ID']);
    expect(first.correlation_id).toBe(captured[0]['X-Correlation-ID']);
    expect(captured[1]['X-Decision-ID']).not.toBe(captured[0]['X-Decision-ID']);
    expect(api.get).toHaveBeenNthCalledWith(1, expect.stringMatching(/\/api\/intelligence\/budget-advisor$/), expect.objectContaining({
      params: expect.objectContaining({ explain: true, budget: 300, market: 'FII', profile: 'CONSERVATIVE' }),
    }));
  });

  test('usa headers de resposta como fallback compatível', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { ...completeBudgetResponse, decision_id: undefined, correlation_id: undefined },
      headers: {
        'x-decision-id': completeBudgetResponse.decision_id,
        'x-correlation-id': completeBudgetResponse.correlation_id,
      },
    } as never);
    const result = await getInvestmentWorkspaceRecommendation({ budget: 300, market: 'FII', profile: 'CONSERVATIVE', includeWarnings: false });
    expect(result.decision_id).toBe(completeBudgetResponse.decision_id);
    expect(result.correlation_id).toBe(completeBudgetResponse.correlation_id);
  });
});

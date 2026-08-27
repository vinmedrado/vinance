import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'vite';

const vite = await createServer({
  appType: 'custom',
  logLevel: 'error',
  server: { middlewareMode: true },
});

const decision = await vite.ssrLoadModule('/src/features/investment-workspace/utils/investmentDecision.ts');
const service = await vite.ssrLoadModule('/src/features/investment-workspace/services/investmentWorkspace.service.ts');

after(async () => {
  await vite.close();
});

test('traduz todas as fronteiras da chance quantitativa', () => {
  const cases = [
    [95, 'Excelente'],
    [94.99, 'Muito alta'],
    [90, 'Muito alta'],
    [89.99, 'Alta'],
    [80, 'Alta'],
    [79.99, 'Boa'],
    [70, 'Boa'],
    [69.99, 'Moderada'],
    [60, 'Moderada'],
    [59.99, 'Baixa'],
  ];

  for (const [score, expected] of cases) {
    assert.equal(decision.quantitativeChance(score), expected);
  }
});

test('aplica a precedência Evitar, Aguardar e Comprar sem alterar o payload', () => {
  const approved = {
    ticker: 'TEST11',
    market: 'FII',
    status: 'APPROVED',
    risk_level: 'LOW',
    recommendation_score: 86,
    confidence_score: 92,
    appreciation_signal: 'HIGH',
    trend_label: 'UPTREND',
    momentum_score: 70,
  };

  assert.equal(decision.suggestedAction(approved).label, 'Comprar');
  assert.equal(decision.suggestedAction({ ...approved, risk_level: 'HIGH' }).label, 'Evitar');
  assert.equal(decision.suggestedAction({ ...approved, status: 'BLOCKED' }).label, 'Evitar');
  assert.equal(decision.suggestedAction({ ...approved, appreciation_signal: 'LOW' }).label, 'Evitar');
  assert.equal(decision.suggestedAction({ ...approved, trend_label: 'SIDEWAYS', momentum_score: 44 }).label, 'Aguardar');
  assert.equal(decision.suggestedAction({ ...approved, trend_label: 'DOWNTREND' }).label, 'Aguardar');
  assert.equal(decision.suggestedAction({ ...approved, trend_label: 'INSUFFICIENT_HISTORY' }).label, 'Aguardar');
  assert.equal(decision.suggestedAction({ ...approved, trend_label: undefined }).label, 'Aguardar');
  assert.equal(decision.suggestedAction({ ...approved, risk_level: 'MEDIUM' }).label, 'Aguardar');
  assert.equal(approved.risk_level, 'LOW');
});

test('mapeia o rating por scores e impede contradição com a ação visual', () => {
  assert.equal(decision.opportunityRating(95, 95).stars, 5);
  assert.equal(decision.opportunityRating(85, 85).stars, 4);
  assert.equal(decision.opportunityRating(75, 75).stars, 3);
  assert.equal(decision.opportunityRating(65, 65).stars, 2);
  assert.equal(decision.opportunityRating(55, 55).stars, 1);
  assert.equal(decision.opportunityRating(95, 95, 'Evitar').stars, 1);
  assert.equal(decision.opportunityRating(95, 95, 'Aguardar').stars, 2);
  assert.equal(decision.opportunityRating(95, null).compositeScore, null);
  assert.equal(decision.opportunityRating(95, null).stars, 0);
  assert.equal(decision.opportunityRating(95, null).label, 'Rating indisponível');
});

test('traduz risco, tendência e potencial com fallback seguro', () => {
  assert.equal(decision.riskLabel('LOW'), 'Baixo');
  assert.equal(decision.riskLabel('unexpected'), 'Indefinido');
  assert.equal(decision.trendLabel('SIDEWAYS'), 'Mercado lateral');
  assert.equal(decision.trendLabel(undefined), 'Tendência indefinida');
  assert.equal(decision.appreciationLabel('MODERATE'), 'Moderado');
  assert.equal(decision.appreciationLabel(undefined), 'Indefinido');
});

test('normaliza listas e recomendações parciais na fronteira da API', () => {
  const normalized = service.normalizeInvestmentWorkspaceResponse({
    budget: 300,
    market: 'FII',
    profile: 'CONSERVATIVE',
    best_recommendation: {
      ticker: 'TEST11',
      market: 'FII',
      why_recommended: ['Motivo válido', 42],
      strengths: 'formato inválido',
      attention_points: ['Atenção válida'],
      comparison_with_alternatives: [
        { ticker: 'ALT11', reason: 'Score inferior' },
        { ticker: 123, reason: null },
      ],
    },
    alternatives: [
      { ticker: 'ALT11', market: 'FII' },
      { ticker: 'SEM_MERCADO' },
    ],
  });

  assert.deepEqual(normalized.best_recommendation?.why_recommended, ['Motivo válido']);
  assert.deepEqual(normalized.best_recommendation?.strengths, []);
  assert.deepEqual(normalized.best_recommendation?.attention_points, ['Atenção válida']);
  assert.deepEqual(normalized.best_recommendation?.comparison_with_alternatives, [
    { ticker: 'ALT11', reason: 'Score inferior' },
  ]);
  assert.equal(normalized.alternatives?.length, 1);
  assert.equal(normalized.alternatives?.[0].ticker, 'ALT11');
  assert.ok(normalized.integration_warnings?.length);
});

test('descarta campos escalares e scores malformados sem quebrar a renderização', () => {
  const normalized = service.normalizeInvestmentWorkspaceResponse({
    best_recommendation: {
      ticker: 'SAFE11',
      market: 'FII',
      risk_level: { invalid: true },
      trend_label: 123,
      recommendation_title: { invalid: true },
      executive_summary: ['invalid'],
      recommendation_score: 140,
      confidence_score: -1,
      relative_position: { text: { invalid: true } },
    },
    alternatives: [],
  });

  assert.equal(normalized.best_recommendation?.risk_level, undefined);
  assert.equal(normalized.best_recommendation?.trend_label, undefined);
  assert.equal(normalized.best_recommendation?.recommendation_title, undefined);
  assert.equal(normalized.best_recommendation?.executive_summary, undefined);
  assert.equal(normalized.best_recommendation?.recommendation_score, undefined);
  assert.equal(normalized.best_recommendation?.confidence_score, undefined);
  assert.equal(normalized.best_recommendation?.relative_position?.text, undefined);
});

test('rejeita uma resposta raiz inválida', () => {
  assert.throws(
    () => service.normalizeInvestmentWorkspaceResponse(null),
    /resposta de recomendação inválida/,
  );
  assert.throws(
    () => service.normalizeInvestmentWorkspaceResponse({ best_recommendation: 'inválida' }),
    /recomendação principal.*estrutura válida/,
  );
});

test('mantém uma única integração com budget-advisor e explain=true', async () => {
  const sourceUrl = new URL('../src/features/investment-workspace/services/investmentWorkspace.service.ts', import.meta.url);
  const source = await readFile(sourceUrl, 'utf8');

  assert.match(source, /const ENDPOINT = `\$\{API_BASE_URL\}\/api\/intelligence\/budget-advisor`/);
  assert.match(source, /api\.get<unknown>\(ENDPOINT/);
  assert.match(source, /explain:\s*true/);
  assert.doesNotMatch(source, /axios\.get/);
});

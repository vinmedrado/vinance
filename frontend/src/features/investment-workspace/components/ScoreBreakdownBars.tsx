import type { CSSProperties } from 'react';
import { Card } from '../../../components';
import type { BudgetRecommendation, ScoreBreakdown } from '../types/investmentWorkspace.types';
import { numberValue, scoreText, scoreTone } from '../utils/investmentDecision';

type ScoreRow = { label: string; value?: number | string };

export function ScoreBreakdownBars({ breakdown, item }: { breakdown?: ScoreBreakdown; item: BudgetRecommendation }) {
  const source = breakdown ?? {};
  const rows: ScoreRow[] = [
    { label: 'Recommendation Score', value: source.recommendation_score ?? item.recommendation_score },
    { label: 'Fundamental Score', value: source.fundamental_score ?? item.score_total },
    { label: 'Profile Score', value: source.profile_score ?? item.profile_score },
    { label: 'Quality Score', value: source.quality_score ?? item.score_quality },
    { label: 'Liquidity Score', value: source.liquidity_score ?? item.score_liquidity },
    { label: 'Risk Score', value: source.risk_score ?? item.score_risk },
    { label: 'Dividend Score', value: source.dividend_score ?? item.score_dividend },
    { label: 'Momentum Score', value: source.momentum_score ?? item.momentum_score },
  ];

  return (
    <Card className="vn-score-breakdown-card" title="Composição dos scores" description="Detalhamento dos oito indicadores retornados pela API.">
      <div className="vn-score-bars">
        {rows.map((row) => {
          const value = numberValue(row.value);
          const width = Math.max(0, Math.min(100, value ?? 0));
          const tone = scoreTone(value);
          const style = { '--vn-bar-value': `${width}%` } as CSSProperties;
          return (
            <div className={`vn-score-bar vn-score-bar--${tone}`} key={row.label} style={style}>
              <div><span>{row.label}</span><strong>{scoreText(row.value)}</strong></div>
              <div
                className="vn-score-bar__track"
                role={value === null ? undefined : 'meter'}
                aria-label={value === null ? `${row.label} não informado` : row.label}
                aria-valuemin={value === null ? undefined : 0}
                aria-valuemax={value === null ? undefined : 100}
                aria-valuenow={value === null ? undefined : width}
              ><span /></div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

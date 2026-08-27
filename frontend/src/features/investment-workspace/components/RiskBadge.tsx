import { CircleHelp, ShieldAlert, ShieldCheck } from 'lucide-react';
import { riskLabel, riskTone } from '../utils/investmentDecision';

export function RiskBadge({ level, showPrefix = true }: { level?: string; showPrefix?: boolean }) {
  const label = riskLabel(level);
  const tone = riskTone(level);
  const RiskIcon = tone === 'success' ? ShieldCheck : tone === 'neutral' ? CircleHelp : ShieldAlert;

  return (
    <span className={`vn-risk-badge vn-risk-badge--${tone}`} aria-label={`Risco ${label}`}>
      <RiskIcon size={14} aria-hidden="true" />
      {showPrefix ? `Risco ${label}` : label}
    </span>
  );
}

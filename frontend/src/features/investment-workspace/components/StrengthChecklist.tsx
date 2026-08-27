import { CheckCircle2, ListChecks } from 'lucide-react';
import { Card } from '../../../components';
type StrengthChecklistProps = {
  title: string;
  items?: string[];
  variant?: 'reasons' | 'strengths';
};

export function StrengthChecklist({ title, items, variant = 'strengths' }: StrengthChecklistProps) {
  return (
    <Card className={`vn-checklist-card vn-checklist-card--${variant}`} title={title} description={variant === 'reasons' ? 'Critérios técnicos considerados na decisão.' : 'Sinais positivos locais; eles não anulam bloqueios da decisão principal.'}>
      {items && items.length > 0 ? (
        <ul className="vn-decision-checklist">
          {items.map((item, index) => <li key={`${index}-${item}`}><CheckCircle2 size={17} aria-hidden="true" /><span>{item}</span></li>)}
        </ul>
      ) : (
        <div className="vn-decision-empty"><ListChecks size={19} aria-hidden="true" /><span>Nenhum item foi informado pela API.</span></div>
      )}
    </Card>
  );
}

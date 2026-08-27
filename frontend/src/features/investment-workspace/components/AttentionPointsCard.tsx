import { AlertTriangle } from 'lucide-react';
import { Card } from '../../../components';

export function AttentionPointsCard({ items }: { items?: string[] }) {
  return (
    <Card className="vn-attention-card" title="Pontos de atenção" description="O que merece cautela antes da decisão.">
      {items && items.length > 0 ? (
        <ul className="vn-attention-list">
          {items.map((item, index) => <li key={`${index}-${item}`}><AlertTriangle size={17} aria-hidden="true" /><span>{item}</span></li>)}
        </ul>
      ) : (
        <div className="vn-decision-empty"><AlertTriangle size={19} aria-hidden="true" /><span>Nenhum ponto de atenção foi informado.</span></div>
      )}
    </Card>
  );
}

import { Card } from './Card';
import { EmptyState } from './EmptyState';
import { formatCurrency, formatPercent, toNumber } from '../utils/formatters';

type AllocationItem = { asset_class: string; percentage: string | number; amount: string | number };

type AllocationCardProps = {
  title?: string;
  description?: string;
  items: AllocationItem[];
  labels?: Record<string, string>;
  emptyDescription?: string;
};

export function AllocationCard({ title = 'Alocação por classe', description = 'Distribuição educacional calculada pelo backend.', items, labels = {}, emptyDescription }: AllocationCardProps) {
  return (
    <Card title={title} description={description}>
      {items.length > 0 ? (
        <div className="vn-allocation vn-allocation--refined">
          {items.map((item) => {
            const pct = Math.max(0, Math.min(100, toNumber(item.percentage)));
            return (
              <div key={item.asset_class}>
                <div>
                  <strong>{labels[item.asset_class] ?? item.asset_class}</strong>
                  <span>{formatPercent(item.percentage)} · {formatCurrency(item.amount)}</span>
                </div>
                <div className="vn-bar" aria-label={`${labels[item.asset_class] ?? item.asset_class}: ${formatPercent(item.percentage)}`}>
                  <span style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState title="Alocação indisponível" description={emptyDescription || 'Ainda não há alocação calculada para este contexto.'} />
      )}
    </Card>
  );
}

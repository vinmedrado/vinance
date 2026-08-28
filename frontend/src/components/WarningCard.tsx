import { AlertTriangle } from 'lucide-react';

type WarningCardProps = { title?: string; description: string; tone?: 'warning' | 'danger' | 'success' };

export function WarningCard({ title = 'Atenção', description, tone = 'warning' }: WarningCardProps) {
  return (
    <div className={`vn-warning-card vn-warning-card--${tone}`}>
      <AlertTriangle size={18} />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}

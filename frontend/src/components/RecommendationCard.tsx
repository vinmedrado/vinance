import { Badge } from './Badge';
import { Card } from './Card';
import { EmptyState } from './EmptyState';
import { formatCurrency, formatPercent } from '../utils/formatters';

type Asset = { ticker: string; name?: string | null; score: number; methodology?: string; reasons?: string[]; missing_fields?: string[] };
type RecommendationCardProps = {
  assetClass: string;
  label: string;
  allocationPercentage: string | number;
  allocationAmount: string | number;
  assets: Asset[];
  message?: string | null;
};

export function RecommendationCard({ assetClass, label, allocationPercentage, allocationAmount, assets, message }: RecommendationCardProps) {
  return (
    <Card title={label} description={`${formatPercent(allocationPercentage)} · ${formatCurrency(allocationAmount)}`} className="vn-recommendation-card">
      {assets.length > 0 ? (
        <div className="vn-list vn-list--ranking">
          {assets.slice(0, 5).map((asset, index) => (
            <div key={`${assetClass}-${asset.ticker}`}>
              <strong><span>{index + 1}. {asset.ticker}</span><Badge tone={asset.score >= 70 ? 'success' : asset.score >= 45 ? 'warning' : 'neutral'}>{asset.score}/100</Badge></strong>
              <span>{asset.name || asset.methodology || 'Ativo ranqueado por metodologia heurística.'}</span>
              {asset.reasons && asset.reasons.length > 0 && <small>{asset.reasons.slice(0, 2).join(' · ')}</small>}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Sem ativos rankeados" description={message || 'Dados de fundamentos ainda não disponíveis. Nenhum ativo foi inventado.'} />
      )}
    </Card>
  );
}

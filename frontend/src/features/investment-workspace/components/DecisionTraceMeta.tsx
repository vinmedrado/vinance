import { Badge } from '../../../components';

type Props = {
  decisionId?: string;
  correlationId?: string;
  generatedAt?: string;
  auditStatus?: string;
};

function dateTime(value?: string) {
  if (!value || !Number.isFinite(Date.parse(value))) return null;
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(value));
}

export function DecisionTraceMeta({ decisionId, correlationId, generatedAt, auditStatus }: Props) {
  if (!decisionId && !correlationId) return null;
  const persisted = auditStatus?.toUpperCase() !== 'FAILED';

  return (
    <details className="vn-decision-trace">
      <summary>
        <span>{persisted ? 'Decisão registrada' : 'Rastreabilidade pendente'}</span>
        <Badge tone={persisted ? 'neutral' : 'warning'}>{decisionId?.slice(0, 8) ?? 'sem ID'}</Badge>
      </summary>
      <dl>
        {generatedAt && <div><dt>Gerada em</dt><dd>{dateTime(generatedAt) ?? '—'}</dd></div>}
        {decisionId && <div><dt>Decision ID</dt><dd><code>{decisionId}</code></dd></div>}
        {correlationId && <div><dt>Correlation ID</dt><dd><code>{correlationId}</code></dd></div>}
      </dl>
      {!persisted && <p role="status">A análise foi concluída, mas a gravação do histórico não foi confirmada.</p>}
    </details>
  );
}

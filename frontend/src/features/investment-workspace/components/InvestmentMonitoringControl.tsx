import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BellRing, Eye, EyeOff, Settings2, Trash2 } from 'lucide-react';
import { Badge, Button, Card, ErrorState, LoadingState, Modal } from '../../../components';
import type { ApiErrorShape } from '../../../services/api';
import {
  createInvestmentAlertSubscription,
  deleteInvestmentAlertSubscription,
  getInvestmentAlertSubscriptions,
  updateInvestmentAlertSubscription,
} from '../services/investmentAlerts.service';
import type {
  InvestmentAlertSubscription,
  InvestmentAlertSubscriptionUpdate,
} from '../types/investmentWorkspace.types';

type Props = {
  userId?: number;
  asset: string;
  decisionId?: string;
};

type PreferenceDraft = Required<Pick<
  InvestmentAlertSubscriptionUpdate,
  | 'alert_on_action_change'
  | 'alert_on_score_change'
  | 'alert_on_confidence_change'
  | 'alert_on_risk_change'
  | 'alert_on_new_opportunity'
  | 'minimum_score_delta'
  | 'minimum_confidence_delta'
  | 'cooldown_minutes'
>>;

const defaultPreferences: PreferenceDraft = {
  alert_on_action_change: true,
  alert_on_score_change: true,
  alert_on_confidence_change: true,
  alert_on_risk_change: true,
  alert_on_new_opportunity: true,
  minimum_score_delta: 5,
  minimum_confidence_delta: 10,
  cooldown_minutes: 180,
};

function draftFromSubscription(subscription: InvestmentAlertSubscription | undefined): PreferenceDraft {
  if (!subscription) return defaultPreferences;
  return {
    alert_on_action_change: subscription.alert_on_action_change,
    alert_on_score_change: subscription.alert_on_score_change,
    alert_on_confidence_change: subscription.alert_on_confidence_change,
    alert_on_risk_change: subscription.alert_on_risk_change,
    alert_on_new_opportunity: subscription.alert_on_new_opportunity,
    minimum_score_delta: subscription.minimum_score_delta,
    minimum_confidence_delta: subscription.minimum_confidence_delta,
    cooldown_minutes: subscription.cooldown_minutes,
  };
}

function mutationError(error: unknown) {
  const apiError = error as ApiErrorShape | null;
  if (apiError?.status === 401 || apiError?.code === 'AUTH_EXPIRED') {
    return 'Sua sessão terminou. Entre novamente para alterar o monitoramento.';
  }
  return apiError?.message ?? 'Não foi possível atualizar o monitoramento.';
}

export function InvestmentMonitoringControl({ userId, asset, decisionId }: Props) {
  const queryClient = useQueryClient();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [draft, setDraft] = useState<PreferenceDraft>(defaultPreferences);
  const queryKey = useMemo(() => ['investment-alert-subscriptions', userId ?? 'anonymous'] as const, [userId]);
  const subscriptions = useQuery({
    queryKey,
    queryFn: ({ signal }) => getInvestmentAlertSubscriptions(signal),
    enabled: Boolean(userId && decisionId),
    retry: false,
    staleTime: 15_000,
  });
  const monitored = subscriptions.data?.items.find((item) => item.asset === asset.toUpperCase());

  useEffect(() => {
    if (settingsOpen) setDraft(draftFromSubscription(monitored));
  }, [settingsOpen, monitored]);

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey });
    await queryClient.invalidateQueries({ queryKey: ['investment-alerts', userId ?? 'anonymous'] });
  }

  const createMutation = useMutation({
    mutationFn: () => createInvestmentAlertSubscription({ asset, source_decision_id: decisionId! }),
    onSuccess: async () => {
      setFeedback(`${asset} passou a ser monitorado.`);
      await refresh();
    },
  });
  const updateMutation = useMutation({
    mutationFn: (payload: InvestmentAlertSubscriptionUpdate) => updateInvestmentAlertSubscription(monitored!.id, payload),
    onSuccess: async () => {
      setFeedback('Preferências de monitoramento atualizadas.');
      await refresh();
      setSettingsOpen(false);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteInvestmentAlertSubscription(monitored!.id),
    onSuccess: async () => {
      setFeedback(`${asset} deixou de ser monitorado.`);
      await refresh();
      setSettingsOpen(false);
    },
  });

  const pending = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;
  const error = createMutation.error ?? updateMutation.error ?? deleteMutation.error;
  const unavailable = !userId || !decisionId;

  return (
    <Card
      className="vn-monitoring-control"
      title="Acompanhar este ativo"
      description="O VinanceOS compara novas decisões auditadas e avisa apenas quando encontra uma mudança relevante. Nenhuma ordem é executada."
      action={monitored ? <Badge tone={monitored.enabled ? 'success' : 'neutral'}>{monitored.enabled ? 'Monitoramento ativo' : 'Monitoramento pausado'}</Badge> : undefined}
    >
      {subscriptions.isLoading && <LoadingState label="Verificando monitoramentos..." />}
      {subscriptions.error && (
        <ErrorState
          title="Monitoramento indisponível"
          description={mutationError(subscriptions.error)}
          action={<Button type="button" variant="secondary" onClick={() => subscriptions.refetch()}>Tentar novamente</Button>}
        />
      )}
      {!subscriptions.isLoading && !subscriptions.error && (
        <div className="vn-monitoring-control__body">
          <div className="vn-monitoring-control__status">
            {monitored ? (monitored.enabled ? <Eye size={19} aria-hidden="true" /> : <EyeOff size={19} aria-hidden="true" />) : <BellRing size={19} aria-hidden="true" />}
            <div>
              <strong>{monitored ? `${asset} está na sua lista` : `Receba alertas sobre ${asset}`}</strong>
              <span>{monitored ? `Revisão diária · cooldown de ${monitored.cooldown_minutes} minutos` : 'A avaliação ocorre após a atualização diária dos sinais.'}</span>
            </div>
          </div>
          <div className="vn-monitoring-control__actions">
            {!monitored ? (
              <Button
                type="button"
                disabled={unavailable || pending}
                onClick={() => { setFeedback(null); createMutation.mutate(); }}
              >
                <BellRing size={17} aria-hidden="true" /> {createMutation.isPending ? 'Ativando...' : 'Monitorar ativo'}
              </Button>
            ) : (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={pending}
                  onClick={() => { setFeedback(null); updateMutation.mutate({ enabled: !monitored.enabled }); }}
                >
                  {monitored.enabled ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                  {monitored.enabled ? 'Pausar' : 'Ativar'}
                </Button>
                <Button type="button" variant="ghost" disabled={pending} onClick={() => setSettingsOpen(true)}>
                  <Settings2 size={17} aria-hidden="true" /> Configurar
                </Button>
              </>
            )}
          </div>
        </div>
      )}
      {unavailable && <p className="vn-monitoring-control__hint">A identificação auditável da decisão é necessária para ativar o acompanhamento.</p>}
      {feedback && <p className="vn-monitoring-feedback" role="status">{feedback}</p>}
      {error && <p className="vn-monitoring-error" role="alert">{mutationError(error)}</p>}

      <Modal open={settingsOpen && Boolean(monitored)} title={`Alertas de ${asset}`} onClose={() => setSettingsOpen(false)}>
        <form
          className="vn-monitoring-preferences"
          onSubmit={(event) => {
            event.preventDefault();
            setFeedback(null);
            updateMutation.mutate(draft);
          }}
        >
          <fieldset>
            <legend>Quando avisar</legend>
            {([
              ['alert_on_new_opportunity', 'Nova oportunidade'],
              ['alert_on_action_change', 'Mudança de ação'],
              ['alert_on_score_change', 'Mudança relevante de score'],
              ['alert_on_confidence_change', 'Mudança relevante de confiança'],
              ['alert_on_risk_change', 'Mudança de risco'],
            ] as const).map(([field, label]) => (
              <label className="vn-check" key={field}>
                <input type="checkbox" checked={draft[field]} onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.checked }))} />
                <span>{label}</span>
              </label>
            ))}
          </fieldset>
          <div className="vn-monitoring-thresholds">
            <label className="vn-field">Variação mínima de score
              <input className="vn-input" type="number" min="1" max="100" step="1" value={draft.minimum_score_delta} onChange={(event) => setDraft((current) => ({ ...current, minimum_score_delta: Number(event.target.value) }))} />
            </label>
            <label className="vn-field">Variação mínima de confiança
              <input className="vn-input" type="number" min="1" max="100" step="1" value={draft.minimum_confidence_delta} onChange={(event) => setDraft((current) => ({ ...current, minimum_confidence_delta: Number(event.target.value) }))} />
            </label>
            <label className="vn-field">Cooldown em minutos
              <input className="vn-input" type="number" min="30" max="10080" step="30" value={draft.cooldown_minutes} onChange={(event) => setDraft((current) => ({ ...current, cooldown_minutes: Number(event.target.value) }))} />
            </label>
          </div>
          <p>Eventos equivalentes são deduplicados. Mudanças críticas materialmente diferentes podem ultrapassar o cooldown.</p>
          {error && <p className="vn-monitoring-error" role="alert">{mutationError(error)}</p>}
          <div className="vn-monitoring-preferences__actions">
            <Button type="button" variant="ghost" disabled={pending} onClick={() => deleteMutation.mutate()}><Trash2 size={16} aria-hidden="true" /> Excluir monitoramento</Button>
            <Button type="submit" disabled={pending}>{updateMutation.isPending ? 'Salvando...' : 'Salvar preferências'}</Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, LockKeyhole, UsersRound } from 'lucide-react';
import { Button, ErrorState, LoadingState, Modal } from '../../../components';
import { useSessionToken } from '../../auth/hooks/useAuth';
import type { Household } from '../../household/types/household.types';
import {
  createFinancialTransferIdempotencyKey,
  useCommitFinancialTransfer,
  usePreviewFinancialTransfer,
} from '../hooks/useFinancialTransfers';
import type { FinancialTransferResource } from '../types/financialState.types';
import { formatCurrency, formatDate } from '../../../utils/formatters';

export function TransferFinancialRecordsDialog({
  open,
  resource,
  recordIds,
  targetHousehold,
  onClose,
  onTransferred,
}: {
  open: boolean;
  resource: FinancialTransferResource;
  recordIds: number[];
  targetHousehold: Household | null;
  onClose: () => void;
  onTransferred: (count: number) => void;
}) {
  const sessionToken = useSessionToken();
  const preview = usePreviewFinancialTransfer();
  const commit = useCommitFinancialTransfer();
  const [duplicateReviewed, setDuplicateReviewed] = useState(false);
  const idempotencyKey = useMemo(
    () => createFinancialTransferIdempotencyKey(resource),
    [open, resource, recordIds.join(',')],
  );

  useEffect(() => {
    setDuplicateReviewed(false);
    preview.reset();
    commit.reset();
    if (!open || !targetHousehold || recordIds.length === 0) return;
    preview.mutate({
      resource,
      targetHouseholdId: targetHousehold.id,
      recordIds,
      sessionToken,
    });
    // Mutation methods are stable in TanStack Query; reopening or changing
    // the selected IDs is the event that must request a new preview.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resource, recordIds.join(','), targetHousehold?.id, sessionToken]);

  const label = resource === 'expenses' ? 'despesa' : 'receita';
  const recordLabel = recordIds.length === 1 ? label : `${label}s`;
  const ownershipAgreement = recordIds.length === 1 ? 'pessoal' : 'pessoais';

  async function confirm() {
    if (!targetHousehold || !preview.data) return;
    const result = await commit.mutateAsync({
      resource,
      targetHouseholdId: targetHousehold.id,
      recordIds,
      duplicateReviewed,
      idempotencyKey,
      sessionToken,
    });
    onTransferred(result.record_count);
  }

  return (
    <Modal open={open} title={`Mover ${recordLabel} para Finanças do casal`} onClose={onClose}>
      <div className="vn-transfer-dialog">
        <div className="vn-transfer-dialog__route" aria-label="Mudança de visibilidade">
          <span><LockKeyhole size={17} aria-hidden="true" /> Minhas finanças</span>
          <b aria-hidden="true">→</b>
          <span><UsersRound size={18} aria-hidden="true" /> Finanças do casal</span>
        </div>
        <p>
          Você selecionou <strong>{recordIds.length} {recordLabel} {ownershipAgreement}</strong>. Os valores, datas e categorias serão preservados em um único lançamento, mas passarão a ser visíveis aos integrantes autorizados de <strong>{targetHousehold?.name}</strong>.
        </p>
        <p className="vn-transfer-dialog__atomic">A transferência é atômica: se um item falhar, nenhum será movido.</p>

        {preview.isPending && <LoadingState label="Verificando lançamentos e possíveis duplicidades…" />}
        {preview.error && <ErrorState title="Não foi possível preparar a transferência" description={preview.error instanceof Error ? preview.error.message : 'Tente novamente.'} />}
        {preview.data && (
          <div className="vn-transfer-dialog__records" role="list" aria-label="Prévia dos lançamentos">
            {preview.data.items.map((item) => (
              <div key={item.record_id} role="listitem">
                <span><strong>{item.description}</strong><small>{formatDate(item.effective_date)}</small></span>
                <b>{formatCurrency(item.amount)}</b>
                {item.possible_duplicates.length > 0 && (
                  <div className="vn-transfer-dialog__duplicate">
                    <AlertTriangle size={17} aria-hidden="true" />
                    <span>
                      <strong>Possível lançamento semelhante</strong>
                      <small>Encontramos {item.possible_duplicates.length} registro(s) parecido(s) nas Finanças do casal. Isso é um aviso para revisão, não uma duplicidade confirmada.</small>
                      <ul aria-label="Lançamentos semelhantes para revisão">
                        {item.possible_duplicates.map((candidate) => (
                          <li key={candidate.candidate_id}>
                            <span>{candidate.description} · {formatDate(candidate.effective_date)}</span>
                            <b>{formatCurrency(candidate.amount)}</b>
                          </li>
                        ))}
                      </ul>
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {preview.data?.requires_duplicate_review && (
          <label className="vn-transfer-dialog__review">
            <input
              type="checkbox"
              checked={duplicateReviewed}
              onChange={(event) => setDuplicateReviewed(event.target.checked)}
            />
            <span>Revisei os possíveis lançamentos semelhantes e quero continuar sem excluir nada.</span>
          </label>
        )}
        {commit.error && <ErrorState title="Nenhum lançamento foi transferido" description={commit.error instanceof Error ? commit.error.message : 'A operação foi revertida. Tente novamente.'} />}
        <div className="vn-inline-actions">
          <Button variant="secondary" onClick={onClose} disabled={commit.isPending}>Cancelar</Button>
          <Button
            onClick={confirm}
            disabled={!preview.data || commit.isPending || (preview.data.requires_duplicate_review && !duplicateReviewed)}
          >
            {commit.isPending ? 'Transferindo…' : 'Confirmar transferência'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

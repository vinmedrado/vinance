import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  commitFinancialRecordTransfer,
  previewFinancialRecordTransfer,
} from '../services/financialState.service';
import type { FinancialTransferResource } from '../types/financialState.types';
import { financialStateQueryKey } from './useFinancialState';

type PreviewRequest = {
  resource: FinancialTransferResource;
  targetHouseholdId: number;
  recordIds: number[];
  sessionToken: string | null;
};

type CommitRequest = PreviewRequest & {
  duplicateReviewed: boolean;
  idempotencyKey: string;
};

function assertSession(expected: string | null, current: string | null) {
  if (expected !== current) throw new Error('A sessão mudou. Reabra a transferência antes de continuar.');
}
function invalidateHousehold(client: ReturnType<typeof useQueryClient>, token: string | null, householdId: number, resource: FinancialTransferResource) {
  for (const key of [
    financialStateQueryKey(token, resource, householdId),
    financialStateQueryKey(token, 'current', householdId),
    ['financial-policy', token, 'current', householdId],
    ['capital-allocation', token, 'current', householdId],
    ['investment-orchestration', token, 'current', householdId],
    ['action-plan', token, 'current', householdId],
    ['continuous-autopilot', token, 'current', householdId],
  ]) client.invalidateQueries({ queryKey: key });
}

export function createFinancialTransferIdempotencyKey(resource: FinancialTransferResource) {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `financial-transfer-${resource}-${random}`;
}

export function usePreviewFinancialTransfer() {
  const token = useSessionToken();
  return useMutation({
    mutationFn: (request: PreviewRequest) => {
      assertSession(request.sessionToken, token);
      return previewFinancialRecordTransfer(request.resource, request.targetHouseholdId, request.recordIds);
    },
  });
}

export function useCommitFinancialTransfer() {
  const token = useSessionToken();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (request: CommitRequest) => {
      assertSession(request.sessionToken, token);
      return commitFinancialRecordTransfer(
        request.resource,
        request.targetHouseholdId,
        request.recordIds,
        request.duplicateReviewed,
        request.idempotencyKey,
      );
    },
    onSuccess: (result, request) => {
      for (const householdId of new Set([...result.source_household_ids, result.target_household_id])) {
        invalidateHousehold(client, request.sessionToken, householdId, request.resource);
      }
    },
  });
}

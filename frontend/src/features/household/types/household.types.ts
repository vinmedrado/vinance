import type { Household } from '../../financial-state/types/financialState.types';

export type { Household };

export type HouseholdRole = 'OWNER' | 'MEMBER';
export type HouseholdMemberStatus = 'ACTIVE' | 'REMOVED';
export type HouseholdInvitationStatus = 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED' | 'EXPIRED';

export type HouseholdMember = {
  id: number;
  household_id: number;
  user_id: number;
  role: HouseholdRole;
  status: HouseholdMemberStatus;
  is_default: boolean;
  joined_at: string;
  updated_at: string;
  email: string | null;
  full_name: string | null;
};

export type HouseholdInvitation = {
  id: number;
  household_id: number;
  household_name: string;
  invited_email_normalized: string;
  invited_user_id: number | null;
  invited_by_user_id: number;
  invited_by_name: string | null;
  role: HouseholdRole;
  status: HouseholdInvitationStatus;
  expires_at: string | null;
  accepted_at: string | null;
  declined_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateHouseholdPayload = { name: string; household_type: 'SHARED' };
export type CreateInvitationPayload = { email: string; role: HouseholdRole };

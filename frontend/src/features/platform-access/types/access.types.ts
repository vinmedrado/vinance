export type AccessCapabilities = {
  access_mode: 'INVITE_ONLY' | 'PUBLIC_VERIFIED';
  public_signup: boolean;
  bootstrap_available: boolean;
  invite_only: boolean;
  email_delivery_available: boolean;
  password_recovery_delivery_available: boolean;
  cloudflare_access_automation_available: boolean;
};

export type PlatformAccessProfile = { is_platform_admin: boolean };

export type CredentialRegistration = {
  full_name: string;
  email: string;
  password: string;
  password_confirmation: string;
  privacy_acknowledged: boolean;
};

export type PlatformInvitation = {
  id: string;
  email_normalized: string;
  status: string;
  delivery_status: string;
  cloudflare_access_status: string;
  expires_at: string;
  accepted_at?: string | null;
  cancelled_at?: string | null;
  resend_count: number;
  created_at: string;
};

export type InvitationIssued = {
  invitation: PlatformInvitation;
  registration_path: string;
  manual_link_required: boolean;
  message: string;
};

export type PlatformUser = {
  id: number;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  is_platform_admin: boolean;
  created_at: string;
};

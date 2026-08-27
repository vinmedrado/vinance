export type User = {
  id: number;
  email: string;
  full_name?: string | null;
  is_active: boolean;
};

export type LoginPayload = { email: string; password: string };
export type RegisterPayload = LoginPayload & { full_name?: string };

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

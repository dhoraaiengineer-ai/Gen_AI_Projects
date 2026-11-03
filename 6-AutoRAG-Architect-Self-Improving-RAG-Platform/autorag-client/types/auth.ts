/**
 * Auth types for E-9 — Login, Signup, Forgot Password.
 * Kept separate from types/index.ts (domain contracts) per monorepo rule:
 * auth concerns are UI-layer only and do not cross into the API contract.
 */

export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface SignupFormData {
  fullName: string;
  email: string;
  password: string;
  organisation: string;
  role: "engineer" | "lead" | "viewer";
}

export interface ForgotPasswordFormData {
  email: string;
}

export type AuthErrorCode =
  | "invalid_credentials"
  | "account_not_found"
  | "expired_link"
  | "email_not_confirmed"
  | "email_already_registered"
  | "unknown";

export const AUTH_ERROR_MESSAGES: Record<AuthErrorCode, string> = {
  invalid_credentials: "Incorrect email or password.",
  account_not_found: "No account found with this email.",
  expired_link: "Reset link has expired. Please request a new one.",
  email_not_confirmed: "Please confirm your email before logging in.",
  email_already_registered: "An account with this email already exists.",
  unknown: "Something went wrong. Please try again.",
};

/** Maps a raw Supabase error message to a typed AuthErrorCode. */
export function mapSupabaseAuthError(message: string): AuthErrorCode {
  const msg = message.toLowerCase();
  if (msg.includes("invalid login credentials") || msg.includes("invalid password")) {
    return "invalid_credentials";
  }
  if (msg.includes("user not found") || msg.includes("no user found")) {
    return "account_not_found";
  }
  if (msg.includes("email not confirmed")) {
    return "email_not_confirmed";
  }
  if (msg.includes("user already registered") || msg.includes("already been registered")) {
    return "email_already_registered";
  }
  if (msg.includes("expired") || msg.includes("invalid token")) {
    return "expired_link";
  }
  return "unknown";
}

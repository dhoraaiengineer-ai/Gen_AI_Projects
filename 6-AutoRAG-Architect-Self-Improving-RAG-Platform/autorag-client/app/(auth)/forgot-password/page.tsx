import { AuthCard } from "@/components/auth/AuthCard";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

/**
 * /forgot-password — sends a Supabase password reset email (E-9).
 * Security: always shows the same success message regardless of whether
 * the email is registered (no user enumeration — Rule 70).
 */
export default function ForgotPasswordPage() {
  return (
    <AuthCard>
      <ForgotPasswordForm />
    </AuthCard>
  );
}

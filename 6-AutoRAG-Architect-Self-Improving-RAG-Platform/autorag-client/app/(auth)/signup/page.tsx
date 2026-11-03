import { AuthCard } from "@/components/auth/AuthCard";
import { SignupForm } from "@/components/auth/SignupForm";

/**
 * /signup — new account registration (E-9).
 * Collects: name, email, password, organisation, role.
 * Social Login (OAuth) is explicitly backlog — not in Sprint 4.
 */
export default function SignupPage() {
  return (
    <AuthCard>
      <SignupForm />
    </AuthCard>
  );
}

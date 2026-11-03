import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AutoRAG Architect — Sign in",
};

/**
 * Auth layout (E-9) — no sidebar, full-height centered card.
 * Root layout already applies bg-bg-main (#030712) and dark class.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

import { AppShell } from "@/components/layout/AppShell";
import { DashboardView } from "@/components/dashboard/DashboardView";

/**
 * /dashboard — pipeline list + KPI cards + HITL queue (E-4).
 * Server component composing the client shell + view (Rule 20: server-first).
 * hideHeaderBar (26-Jul-2026): DashboardView's own WelcomeHero already is a
 * full page hero (badge, title, description, CTAs, status chips) -- showing
 * the shared PageHero above it duplicated the same title/description twice.
 */
export default function DashboardPage() {
  return (
    <AppShell title="Dashboard" hideHeaderBar>
      <DashboardView />
    </AppShell>
  );
}

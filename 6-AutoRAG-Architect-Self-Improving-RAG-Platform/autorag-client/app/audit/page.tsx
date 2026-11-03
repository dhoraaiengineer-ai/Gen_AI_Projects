import { AppShell } from "@/components/layout/AppShell";
import { AuditLogsTable } from "@/components/audit/AuditLogsTable";

/**
 * /audit — Audit Logs (E-13).
 * Server component: wraps AppShell + defers all interactivity to AuditLogsTable.
 * Audit log viewer (E-13).
 */
export default function AuditPage() {
  return (
    <AppShell
      title="Audit Logs"
      description="Immutable, INSERT-ONLY event history for pipeline lifecycle, deployment, and safety actions."
    >
      <AuditLogsTable />
    </AppShell>
  );
}

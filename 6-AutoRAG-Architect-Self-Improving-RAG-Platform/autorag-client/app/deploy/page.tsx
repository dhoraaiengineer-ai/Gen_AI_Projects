import { AppShell } from "@/components/layout/AppShell";
import { DeploymentCenter } from "@/components/deployment/DeploymentCenter";

/**
 * /deploy — Deployment Center (E-12).
 * Server component: wraps AppShell + defers all interactivity to DeploymentCenter.
 * Deployment Center (E-12).
 */
export default function DeployPage() {
  return (
    <AppShell
      title="Approve & Deploy"
      description="Review the readiness gate, approve HITL runs, and promote with zero-downtime Blue/Green deployment — rollback is one click away."
    >
      <DeploymentCenter />
    </AppShell>
  );
}

import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// ChatPageClient (components/chat/) preserved untouched for future real
// wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
export default function ChatPage() {
  return (
    <AppShell title="AI Chat Playground">
      <AdvancedFeaturePlaceholder
        feature="AI Chat Playground"
        relatedScreens={[{ label: "Retrieval", href: "/retrieve" }]}
      />
    </AppShell>
  );
}

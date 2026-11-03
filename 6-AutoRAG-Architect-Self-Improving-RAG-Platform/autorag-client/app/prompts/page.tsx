import { AppShell } from "@/components/layout/AppShell";
import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

// PromptStudioPageClient (components/prompts/) preserved untouched for future
// real wiring — see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
export default function PromptsPage() {
  return (
    <AppShell title="Prompt Studio">
      <AdvancedFeaturePlaceholder feature="Prompt Studio" />
    </AppShell>
  );
}

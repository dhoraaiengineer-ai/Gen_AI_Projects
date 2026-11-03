import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

/**
 * /settings/api-keys — Chapter 26.14 API Keys.
 *
 * 20-Jul-2026: previously rendered a hardcoded DEMO_KEYS table (fake key
 * masks, fake "last used" dates, fake "created by" names) with zero backend
 * call — undisclosed fabrication inside an otherwise-real Settings page,
 * found via a full frontend-pages audit. No API key management endpoint
 * exists on the backend (routes/ has no api_key/api-key route), so this
 * follows the same honest-placeholder pattern as the other deferred pages
 * (chunks/, embeddings/, etc.) rather than inventing a different set of
 * fake data. Real provider configuration (which LLM/embedding/reranker is
 * actually active) already lives on Organization — pointed to below.
 */
export function ApiKeysPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">API Keys</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage provider API keys. Keys are always stored masked.
        </p>
      </div>
      <AdvancedFeaturePlaceholder
        feature="API Key Management"
        relatedScreens={[{ label: "Organization", href: "/settings/organization" }]}
      />
    </div>
  );
}

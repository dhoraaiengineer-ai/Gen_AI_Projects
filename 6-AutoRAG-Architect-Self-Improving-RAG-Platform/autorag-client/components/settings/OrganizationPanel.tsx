"use client";

import { SettingsCard } from "./SettingsCard";

const ORG = {
  name: "AutoRAG Architect",
  id: process.env.NEXT_PUBLIC_DEFAULT_ORG_ID ?? "—",
  subscription: "Enterprise",
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? "development",
  region: "ap-south-1",
};

/** /settings/organization — Chapter 26.8 Organization Settings. */
export function OrganizationPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Organization</h2>
        <p className="text-sm text-muted-foreground mt-1">
          View and manage your organization configuration.
        </p>
      </div>

      <SettingsCard title="Organization Details">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
          {[
            { label: "Name",         value: ORG.name },
            { label: "Organization ID", value: ORG.id },
            { label: "Subscription", value: ORG.subscription },
            { label: "Environment",  value: ORG.environment },
            { label: "Region",       value: ORG.region },
          ].map(({ label, value }) => (
            <div key={label}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-medium mt-0.5 font-mono text-xs">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-5 flex gap-2">
          <button className="rounded-md bg-orange-500 px-4 py-2 text-sm font-medium text-foreground hover:bg-orange-600 transition-colors">
            Update Profile
          </button>
          <button className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
            Configure Domains
          </button>
        </div>
      </SettingsCard>

      <SettingsCard title="AI Provider Stack" description="Active provider configuration (read-only — managed via .env).">
        <div className="space-y-3 text-sm">
          {[
            { label: "Primary LLM",   value: "Gemini Flash 3.5",   status: "active" },
            { label: "Fallback LLM",  value: "KiMi K2.6",          status: "standby" },
            { label: "Embeddings",    value: "Gemini Embedding 2",  status: "active" },
            { label: "Reranker",      value: "Cohere Rerank v3",    status: "active" },
          ].map(({ label, value, status }) => (
            <div key={label} className="flex items-center justify-between rounded-lg border px-3 py-2">
              <span className="text-muted-foreground">{label}</span>
              <div className="flex items-center gap-2">
                <span className="font-medium">{value}</span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    status === "active"
                      ? "bg-green-500/10 text-green-600 dark:text-green-400"
                      : "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                  }`}
                >
                  {status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </SettingsCard>
    </div>
  );
}

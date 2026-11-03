import { AdvancedFeaturePlaceholder } from "@/components/ui/advanced-feature-placeholder";

/**
 * /settings/members — Chapter 26.9 User Management.
 *
 * 20-Jul-2026: previously rendered a hardcoded DEMO_MEMBERS table (invented
 * team members, fake emails, fake "last login" dates) with zero backend
 * call — undisclosed fabrication inside an otherwise-real Settings page,
 * found via a full frontend-pages audit. No team/member management endpoint
 * exists on the backend, so this follows the same honest-placeholder
 * pattern as the other deferred pages (chunks/, embeddings/, etc.) rather
 * than inventing a different set of fake data. The signed-in user's own
 * real account already lives on Profile — pointed to below.
 */
export function MembersPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Members</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage team members, roles, and access control.
        </p>
      </div>
      <AdvancedFeaturePlaceholder
        feature="Team Member Management"
        relatedScreens={[{ label: "Profile", href: "/settings/profile" }]}
      />
    </div>
  );
}

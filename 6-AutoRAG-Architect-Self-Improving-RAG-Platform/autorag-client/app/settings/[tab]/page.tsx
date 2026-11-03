import { notFound } from "next/navigation";
import { ProfilePanel } from "@/components/settings/ProfilePanel";
import { OrganizationPanel } from "@/components/settings/OrganizationPanel";
import { NotificationsPanel } from "@/components/settings/NotificationsPanel";
import { ApiKeysPanel } from "@/components/settings/ApiKeysPanel";
import { MembersPanel } from "@/components/settings/MembersPanel";
import { ThemePanel } from "@/components/settings/ThemePanel";

const TAB_COMPONENTS: Record<string, React.ComponentType> = {
  profile: ProfilePanel,
  organization: OrganizationPanel,
  notifications: NotificationsPanel,
  "api-keys": ApiKeysPanel,
  members: MembersPanel,
  theme: ThemePanel,
};

interface Props {
  params: Promise<{ tab: string }>;
}

/**
 * /settings/[tab] — dynamic settings panel router (E-14).
 * Valid tabs: profile | organization | notifications | api-keys | members | theme
 */
export default async function SettingsTabPage({ params }: Props) {
  const { tab } = await params;
  const Panel = TAB_COMPONENTS[tab];
  if (!Panel) notFound();
  return <Panel />;
}

export function generateStaticParams() {
  return Object.keys(TAB_COMPONENTS).map((tab) => ({ tab }));
}

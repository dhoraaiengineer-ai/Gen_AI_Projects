import { AppShell } from "@/components/layout/AppShell";
import { SettingsSidebar } from "@/components/settings/SettingsSidebar";

/**
 * Settings shell — shared layout for all /settings/* sub-routes (E-14).
 * Settings sidebar (E-14).
 */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell title="Settings & Administration">
      <div className="flex gap-6 min-h-[calc(100vh-8rem)]">
        <SettingsSidebar />
        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </AppShell>
  );
}

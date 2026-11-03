"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  User,
  Building2,
  Bell,
  Palette,
} from "lucide-react";
import { cn } from "@/lib/utils";

// 26-Jul-2026, per direct product review: Members and API Keys have no real
// backend (no team/RBAC endpoint, no key-management endpoint) -- both
// already avoid fabricated data (AdvancedFeaturePlaceholder, see
// MembersPanel.tsx/ApiKeysPanel.tsx's own dated comments), but showing an
// empty placeholder tab in the nav still invites "why doesn't this work?"
// confusion. Hidden from the sidebar until real backends exist, same
// precedent as /chunks and /embeddings (VERSION_5_ROADMAP.md §4) -- the
// routes themselves are untouched, so a direct link still resolves.
const SETTINGS_TABS = [
  { tab: "profile",       label: "Profile",        icon: User },
  { tab: "organization",  label: "Organization",   icon: Building2 },
  { tab: "notifications", label: "Notifications",  icon: Bell },
  { tab: "theme",         label: "Theme",          icon: Palette },
];

export function SettingsSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-52 shrink-0">
      <nav className="flex flex-col gap-1">
        {SETTINGS_TABS.map(({ tab, label, icon: Icon }) => {
          const href = `/settings/${tab}`;
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={tab}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-orange-500/10 text-orange-500"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NAVIGATION, type NavItem } from "@/lib/navigation";
import { APP_NAME } from "@/lib/constants";
import { useCurrentUser, useSystemStatus } from "@/hooks/use-api";
import { Avatar, AvatarFallback, Tooltip } from "@/components/ui/primitives";
import { StatusDot } from "@/components/shared/status";
import { cn } from "@/lib/utils";

export function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring" aria-label={`${APP_NAME} home`}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[#3c6fe0] to-[#1f4fa3] text-[15px] text-white shadow-sm" aria-hidden>
        ◈
      </span>
      {!collapsed && <span className="text-[15px] font-semibold tracking-tight text-white">{APP_NAME}</span>}
    </Link>
  );
}

function NavLink({ item, collapsed, active, onNavigate }: { item: NavItem; collapsed: boolean; active: boolean; onNavigate?: () => void }) {
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-9 items-center gap-3 rounded-md px-2.5 text-[13px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-white",
        collapsed && "justify-center px-0",
      )}
    >
      {active && <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-[#5b8cf0]" aria-hidden />}
      <item.icon className={cn("size-4 shrink-0", active ? "text-white" : "text-sidebar-muted group-hover:text-white", item.href === "/copilot" && "text-[#7fa5f5]")} aria-hidden />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && item.href === "/copilot" && (
        <span className="ml-auto rounded bg-[#2f62d6]/25 px-1.5 py-px text-[10px] font-semibold tracking-wide text-[#a9c3f8]">AI</span>
      )}
    </Link>
  );
  return collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

export function SidebarContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: status } = useSystemStatus();
  const { data: user } = useCurrentUser();
  const operational = !status || status.status === "operational";
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="flex h-full flex-col">
      <div className={cn("flex h-14 items-center px-4", collapsed && "justify-center px-0")}>
        <Logo collapsed={collapsed} />
      </div>
      <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 pt-3 pb-4">
        {NAVIGATION.map((section, i) => (
          <div key={section.title ?? i}>
            {section.title &&
              (collapsed ? (
                <div className="mx-auto mb-2 h-px w-6 bg-sidebar-border" aria-hidden />
              ) : (
                <p className="mb-1.5 px-2.5 text-[11px] font-medium tracking-wider text-sidebar-muted uppercase">{section.title}</p>
              ))}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.href}>
                  <NavLink item={item} collapsed={collapsed} active={isActive(item.href)} onNavigate={onNavigate} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="space-y-1 border-t border-sidebar-border p-3">
        <Link
          href="/agents"
          onClick={onNavigate}
          className={cn("flex items-center gap-2 rounded-md px-2.5 py-2 text-xs text-sidebar-foreground transition-colors hover:bg-sidebar-accent/60", collapsed && "justify-center px-0")}
        >
          <StatusDot tone={operational ? "success" : "warning"} pulse={operational} />
          {!collapsed && <span>{operational ? "System Operational" : "Partial Degradation"}</span>}
        </Link>
        <Link
          href="/settings"
          onClick={onNavigate}
          className={cn("flex items-center gap-2.5 rounded-md px-2 py-1.5 transition-colors hover:bg-sidebar-accent/60", collapsed && "justify-center px-0")}
        >
          <Avatar className="size-7">
            <AvatarFallback className="bg-[#1f3a63] text-[11px] text-white">{user?.initials ?? "··"}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-medium text-white">{user?.name ?? "Loading…"}</span>
              <span className="block truncate text-[11px] text-sidebar-muted capitalize">{user?.role ?? ""}</span>
            </span>
          )}
        </Link>
      </div>
    </div>
  );
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={cn(
        "sticky top-0 z-30 hidden h-dvh shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 lg:flex",
        collapsed ? "w-[68px]" : "w-60",
      )}
    >
      <SidebarContent collapsed={collapsed} />
      <button
        type="button"
        onClick={onToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="absolute top-[18px] -right-3 flex size-6 cursor-pointer items-center justify-center rounded-full border bg-card text-muted-foreground shadow-card transition-colors hover:text-foreground"
      >
        {collapsed ? <PanelLeftOpen className="size-3.5" /> : <PanelLeftClose className="size-3.5" />}
      </button>
    </aside>
  );
}

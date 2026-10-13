"use client";
// View: application frame — sidebar navigation filtered by the user's permissions, top bar with
// the signed-in user, and the disclaimer on every page.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { API_MODE, DISCLAIMER } from "@/lib/config";
import { label } from "@/lib/format";
import type { Me } from "@/types";

export const NAV: { href: string; label: string; permission: string; icon: string }[] = [
  { href: "/", label: "Overview", permission: "dashboard:read", icon: "◧" },
  { href: "/assistant", label: "Assistant", permission: "agents:run", icon: "✦" },
  { href: "/portfolios", label: "Portfolios", permission: "dashboard:read", icon: "▤" },
  { href: "/approvals", label: "Approvals", permission: "portfolio:propose", icon: "✓" },
  { href: "/knowledge", label: "Knowledge base", permission: "dashboard:read", icon: "❏" },
  { href: "/markets", label: "Markets", permission: "dashboard:read", icon: "↗" },
  { href: "/fraud", label: "Fraud", permission: "fraud:analyze", icon: "⚑" },
  { href: "/agents", label: "Agents & system", permission: "dashboard:read", icon: "⚙" },
  { href: "/audit", label: "Audit", permission: "audit:read", icon: "☰" },
];

export function AppShell({ me, onSignOut, children }: { me: Me; onSignOut: () => void; children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const can = (p: string) => me.permissions.includes(p) || (p === "portfolio:propose" && me.permissions.includes("approvals:decide"));
  const items = NAV.filter((n) => can(n.permission));
  const active = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="flex min-h-screen">
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-60 shrink-0 border-r border-white/10 bg-panel p-4 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="mb-6">
          <div className="text-lg font-semibold tracking-tight">FinAgent</div>
          <div className="text-xs text-muted">Multi-agent intelligence</div>
        </div>
        <nav aria-label="Main" className="space-y-1">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              aria-current={active(item.href) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${active(item.href) ? "bg-accent/15 text-accent" : "text-muted hover:bg-white/5 hover:text-white"}`}
            >
              <span aria-hidden className="w-4 text-center">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      {open && <button aria-label="Close menu" className="fixed inset-0 z-20 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <button aria-label="Open menu" className="rounded-lg border border-white/10 px-2 py-1 lg:hidden" onClick={() => setOpen(true)}>☰</button>
          <p className="hidden text-xs text-muted sm:block">
            {DISCLAIMER}
            {API_MODE === "mock" && <span className="ml-2 rounded bg-warn/20 px-1.5 py-0.5 text-warn">mock data</span>}
          </p>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted">
              {me.email} · <span className="text-accent">{label(me.role)}</span>
            </span>
            <button onClick={onSignOut} className="rounded-lg border border-white/10 px-3 py-1 hover:border-accent">Sign out</button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6">{children}</main>
      </div>
    </div>
  );
}

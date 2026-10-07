"use client";

import { useTheme } from "next-themes";
import { KeyRound, Monitor, Moon, Shield, Sun } from "lucide-react";
import { useCurrentUser, useSystemStatus } from "@/hooks/use-api";
import { useIsClient, useStoredState } from "@/hooks/use-client-state";
import { DATA_SOURCE } from "@/lib/constants";
import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/data";
import { Avatar, AvatarFallback, Label, Skeleton, Switch } from "@/components/ui/primitives";
import { StatusDot } from "@/components/shared/status";
import { cn, fmt } from "@/lib/utils";

const ROLE_PERMISSIONS: Record<string, string[]> = {
  viewer: ["View dashboards and inventory", "Ask the Copilot (no prices)"],
  analyst: ["Everything a viewer can do", "Supplier prices and reorder maths", "Web research agent"],
  approver: ["Everything an analyst can do", "Approve or reject PO drafts"],
  admin: ["Everything an approver can do", "Upload and delete documents", "Manage users and settings"],
};

const PREFS_KEY = "supplyai.prefs";
const DEFAULT_PREFS = { criticalAlerts: true, dailyDigest: true, aiInsights: true };

export default function SettingsPage() {
  const { data: user } = useCurrentUser();
  const { data: status, isLoading } = useSystemStatus();
  const { theme, setTheme } = useTheme();
  const mounted = useIsClient();
  const [prefs, setPrefs] = useStoredState(PREFS_KEY, DEFAULT_PREFS);
  const update = (key: keyof typeof prefs, value: boolean) => setPrefs({ ...prefs, [key]: value });

  return (
    <>
      <PageHeader title="Settings" description="Profile, preferences and system status." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Profile</CardTitle>
                <CardDescription>Your identity and role come from your organisation&apos;s sign-in provider</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <Avatar className="size-14">
                <AvatarFallback className="bg-primary text-base text-primary-foreground">{user?.initials ?? "··"}</AvatarFallback>
              </Avatar>
              <div className="flex-1 space-y-3">
                {user ? (
                  <>
                    <div>
                      <p className="text-[15px] font-semibold">{user.name}</p>
                      <p className="text-[13px] text-muted-foreground">{user.email}</p>
                    </div>
                    <div>
                      <p className="flex items-center gap-1.5 text-[12.5px] font-medium">
                        <Shield className="size-3.5 text-muted-foreground" aria-hidden /> Role: <span className="capitalize">{user.role}</span>
                      </p>
                      <ul className="mt-1.5 grid gap-1 text-[12.5px] text-muted-foreground sm:grid-cols-2">
                        {ROLE_PERMISSIONS[user.role].map((p) => (
                          <li key={p}>• {p}</li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : (
                  <Skeleton className="h-12 w-60" />
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Appearance</CardTitle>
                <CardDescription>Choose how SupplyAI looks to you</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {mounted && (
                <Segmented
                  label="Theme"
                  value={(theme as "light" | "dark" | "system") ?? "light"}
                  onChange={setTheme}
                  options={[
                    { value: "light", label: "Light" },
                    { value: "dark", label: "Dark" },
                    { value: "system", label: "System" },
                  ]}
                />
              )}
              <p className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <Sun className="size-3.5" aria-hidden /> <Moon className="size-3.5" aria-hidden /> <Monitor className="size-3.5" aria-hidden /> System follows your OS setting.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>Which agent alerts reach you</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="divide-y">
              {(
                [
                  ["criticalAlerts", "Critical alerts", "Stockout risks and failed workflows, immediately"],
                  ["aiInsights", "AI insights", "Supplier and demand insights from your agents"],
                  ["dailyDigest", "Daily digest", "A morning summary of risks and recommendations"],
                ] as const
              ).map(([key, title, desc]) => (
                <div key={key} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div>
                    <Label htmlFor={key}>{title}</Label>
                    <p className="mt-1 text-[12.5px] text-muted-foreground">{desc}</p>
                  </div>
                  <Switch id={key} checked={prefs[key]} onCheckedChange={(v) => update(key, v)} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>System status</CardTitle>
                <CardDescription>{status ? `Version ${status.version} · ${status.environment}` : "Checking services…"}</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading || !status ? (
                <div className="space-y-3">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-4 w-full" />
                  ))}
                </div>
              ) : (
                <ul className="space-y-2.5">
                  {status.services.map((s) => (
                    <li key={s.name} className="flex items-center justify-between text-[13px]">
                      <StatusDot tone={s.status === "operational" ? "success" : s.status === "degraded" ? "warning" : "critical"} label={s.name} />
                      <span className={cn("text-xs tabular", s.status === "operational" ? "text-muted-foreground" : "font-medium text-warning-foreground")}>
                        {s.status === "operational" ? fmt.ms(s.latencyMs) : `Degraded · ${fmt.ms(s.latencyMs)}`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Data source</CardTitle>
                <CardDescription>Where this workspace reads its data</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-[13px]">
              <p className="flex items-center gap-2 font-medium">
                <KeyRound className="size-4 text-muted-foreground" aria-hidden />
                {DATA_SOURCE === "mock" ? "Demo dataset" : "Live backend (FastAPI)"}
              </p>
              <p className="text-muted-foreground">
                {DATA_SOURCE === "mock"
                  ? "Realistic generated data for demonstrations. Set NEXT_PUBLIC_DATA_SOURCE=api to connect to the live multi-agent backend."
                  : "Connected through the secure API proxy. Agent runs stream from LangGraph in real time."}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

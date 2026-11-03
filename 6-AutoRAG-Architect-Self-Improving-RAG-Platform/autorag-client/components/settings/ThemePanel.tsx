"use client";

import { useState, useEffect } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { SettingsCard } from "./SettingsCard";

type ThemeMode = "light" | "dark" | "system";

/** /settings/theme — Chapter 26.14 System Preferences / dark-mode toggle. */
export function ThemePanel() {
  const [mode, setMode] = useState<ThemeMode>("dark");
  const [compact, setCompact] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem("theme") ?? "dark") as ThemeMode;
    setMode(stored);
  }, []);

  function applyTheme(next: ThemeMode) {
    setMode(next);
    localStorage.setItem("theme", next);
    const root = document.documentElement;
    if (next === "dark") root.setAttribute("data-theme", "dark");
    else if (next === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
  }

  const MODES: { key: ThemeMode; label: string; icon: React.ReactNode }[] = [
    { key: "light",  label: "Light",  icon: <Sun className="h-4 w-4" /> },
    { key: "dark",   label: "Dark",   icon: <Moon className="h-4 w-4" /> },
    { key: "system", label: "System", icon: <Monitor className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Theme</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Customize the appearance of the AutoRAG Architect dashboard.
        </p>
      </div>

      <SettingsCard title="Color Mode">
        <div className="flex gap-3">
          {MODES.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => applyTheme(key)}
              className={`flex flex-1 flex-col items-center gap-2 rounded-lg border p-4 text-sm font-medium transition-colors ${
                mode === key
                  ? "border-orange-500 bg-orange-500/10 text-orange-500"
                  : "hover:bg-muted"
              }`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>
      </SettingsCard>

      <SettingsCard title="Display Preferences">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Compact Mode</p>
              <p className="text-xs text-muted-foreground mt-0.5">Reduce padding in tables and cards</p>
            </div>
            <button
              role="switch"
              aria-checked={compact}
              onClick={() => setCompact((v) => !v)}
              className={`relative inline-flex h-5 w-9 cursor-pointer rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
                compact ? "bg-orange-500" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform mt-0.5 ${
                  compact ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Reduced Motion</p>
              <p className="text-xs text-muted-foreground mt-0.5">Disable transitions and animations</p>
            </div>
            <button
              role="switch"
              aria-checked={reducedMotion}
              onClick={() => setReducedMotion((v) => !v)}
              className={`relative inline-flex h-5 w-9 cursor-pointer rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
                reducedMotion ? "bg-orange-500" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform mt-0.5 ${
                  reducedMotion ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        </div>
      </SettingsCard>
    </div>
  );
}

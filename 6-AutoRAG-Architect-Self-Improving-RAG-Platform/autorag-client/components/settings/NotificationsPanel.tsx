"use client";

import { useEffect, useState } from "react";
import { SettingsCard } from "./SettingsCard";

const LS_KEY = "autorag:notification_prefs";

type Channel = "email" | "slack" | "webhook";
type EventKey =
  | "deploy_started"
  | "deploy_completed"
  | "rollback_triggered"
  | "eval_completed"
  | "cost_limit_exceeded"
  | "guardrail_blocked";

const EVENTS: { key: EventKey; label: string }[] = [
  { key: "deploy_started",      label: "Deployment started" },
  { key: "deploy_completed",    label: "Deployment completed" },
  { key: "rollback_triggered",  label: "Rollback triggered" },
  { key: "eval_completed",      label: "Evaluation completed" },
  { key: "cost_limit_exceeded", label: "Cost limit exceeded" },
  { key: "guardrail_blocked",   label: "Guardrail blocked" },
];

const DEFAULT_ENABLED: Record<EventKey, boolean> = {
  deploy_started:      true,
  deploy_completed:    true,
  rollback_triggered:  true,
  eval_completed:      false,
  cost_limit_exceeded: true,
  guardrail_blocked:   true,
};

/** /settings/notifications — Chapter 26.16 Notification Settings. Persisted to localStorage. */
export function NotificationsPanel() {
  const [channel, setChannel] = useState<Channel>("email");
  const [enabled, setEnabled] = useState<Record<EventKey, boolean>>(DEFAULT_ENABLED);
  const [webhook, setWebhook] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as { channel?: Channel; enabled?: Record<EventKey, boolean>; webhook?: string };
        if (parsed.channel) setChannel(parsed.channel);
        if (parsed.enabled) setEnabled(parsed.enabled);
        if (parsed.webhook) setWebhook(parsed.webhook);
      }
    } catch {
      // corrupt localStorage — silently ignore, use defaults
    }
  }, []);

  function savePreferences() {
    localStorage.setItem(LS_KEY, JSON.stringify({ channel, enabled, webhook }));
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const toggle = (key: EventKey) =>
    setEnabled((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Notifications</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Configure when and where AutoRAG sends alerts.
        </p>
      </div>

      <SettingsCard title="Delivery Channel">
        <div className="flex gap-3">
          {(["email", "slack", "webhook"] as Channel[]).map((c) => (
            <button
              key={c}
              onClick={() => setChannel(c)}
              className={`rounded-md border px-4 py-2 text-sm font-medium capitalize transition-colors ${
                channel === c
                  ? "border-orange-500 bg-orange-500/10 text-orange-500"
                  : "hover:bg-muted"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        {channel === "webhook" && (
          <div className="mt-4 grid gap-1.5">
            <label className="text-sm font-medium">Webhook URL</label>
            <input
              type="url"
              placeholder="https://hooks.example.com/..."
              value={webhook}
              onChange={(e) => setWebhook(e.target.value)}
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
          </div>
        )}
      </SettingsCard>

      <SettingsCard title="Event Subscriptions" description="Choose which events trigger notifications.">
        <div className="divide-y">
          {EVENTS.map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between py-3">
              <span className="text-sm">{label}</span>
              <button
                role="switch"
                aria-checked={enabled[key]}
                onClick={() => toggle(key)}
                className={`relative inline-flex h-5 w-9 cursor-pointer rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 ${
                  enabled[key] ? "bg-orange-500" : "bg-muted"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform mt-0.5 ${
                    enabled[key] ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={savePreferences}
            className="rounded-md bg-orange-500 px-4 py-2 text-sm font-medium text-foreground hover:bg-orange-600 transition-colors"
          >
            Save Preferences
          </button>
          {saved && <span className="text-sm text-green-500 font-medium">Saved!</span>}
        </div>
      </SettingsCard>
    </div>
  );
}

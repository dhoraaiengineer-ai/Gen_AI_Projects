"use client";

import { useEffect, useState } from "react";
import { createSupabaseClient } from "@/lib/supabase";
import { SettingsCard } from "./SettingsCard";

/** /settings/profile — Chapter 26.7 General + personal user settings. Wired to Supabase Auth. */
export function ProfilePanel() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [saved, setSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwSaved, setPwSaved] = useState(false);
  const [isSavingPw, setIsSavingPw] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createSupabaseClient();
    void supabase.auth.getUser().then(({ data }) => {
      if (data.user) {
        setEmail(data.user.email ?? "");
        setName((data.user.user_metadata?.full_name as string | undefined) ?? "");
        setTimezone(
          (data.user.user_metadata?.timezone as string | undefined) ?? "Asia/Kolkata",
        );
      }
    });
  }, []);

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setProfileError(null);
    try {
      const supabase = createSupabaseClient();
      const { error } = await supabase.auth.updateUser({
        data: { full_name: name, timezone },
      });
      if (error) throw error;
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUpdatePassword() {
    if (!newPw) return;
    setIsSavingPw(true);
    setPwError(null);
    try {
      const supabase = createSupabaseClient();
      const { error } = await supabase.auth.updateUser({ password: newPw });
      if (error) throw error;
      setCurrentPw("");
      setNewPw("");
      setPwSaved(true);
      setTimeout(() => setPwSaved(false), 2500);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setIsSavingPw(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Profile</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your personal account details and preferences.
        </p>
      </div>

      <SettingsCard title="Personal Information" description="Your display name and contact email.">
        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="grid gap-1.5">
            <label className="text-sm font-medium" htmlFor="full-name">
              Full Name
            </label>
            <input
              id="full-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
          </div>
          <div className="grid gap-1.5">
            <label className="text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              disabled
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm text-muted-foreground opacity-60 cursor-not-allowed"
            />
            <p className="text-xs text-muted-foreground">
              Email is managed by Supabase Auth and cannot be edited here.
            </p>
          </div>
          <div className="grid gap-1.5">
            <label className="text-sm font-medium" htmlFor="timezone">
              Timezone
            </label>
            <select
              id="timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-orange-500"
            >
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York (ET)</option>
              <option value="Europe/London">Europe/London (GMT)</option>
            </select>
          </div>
          {profileError && (
            <p role="alert" className="text-sm text-red-500">{profileError}</p>
          )}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={isSaving}
              className="rounded-md bg-orange-500 px-4 py-2 text-sm font-medium text-foreground hover:bg-orange-600 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {isSaving ? "Saving…" : "Save Changes"}
            </button>
            {saved && <span className="text-sm text-green-500 font-medium">Saved!</span>}
          </div>
        </form>
      </SettingsCard>

      <SettingsCard title="Password" description="Update your account password.">
        <div className="space-y-3">
          <div className="grid gap-1.5">
            <label className="text-sm font-medium" htmlFor="current-pw">
              Current Password
            </label>
            <input
              id="current-pw"
              type="password"
              placeholder="••••••••"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
          </div>
          <div className="grid gap-1.5">
            <label className="text-sm font-medium" htmlFor="new-pw">
              New Password
            </label>
            <input
              id="new-pw"
              type="password"
              placeholder="••••••••"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
          </div>
          {pwError && (
            <p role="alert" className="text-sm text-red-500">{pwError}</p>
          )}
          <div className="flex items-center gap-3 pt-1">
            <button
              type="button"
              disabled={isSavingPw || !newPw}
              onClick={handleUpdatePassword}
              className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              {isSavingPw ? "Updating…" : "Update Password"}
            </button>
            {pwSaved && <span className="text-sm text-green-500 font-medium">Password updated!</span>}
          </div>
        </div>
      </SettingsCard>
    </div>
  );
}

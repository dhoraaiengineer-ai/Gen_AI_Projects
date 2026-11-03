import { redirect } from "next/navigation";

/** /settings → /settings/profile */
export default function SettingsRootPage() {
  redirect("/settings/profile");
}

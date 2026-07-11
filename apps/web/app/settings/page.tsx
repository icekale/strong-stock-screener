import { redirect } from "next/navigation";

export default function SettingsPage() {
  redirect("/system?tab=data");
}

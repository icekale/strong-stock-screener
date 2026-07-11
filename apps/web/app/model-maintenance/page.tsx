import { redirect } from "next/navigation";

export default function ModelMaintenancePage() {
  redirect("/system?tab=model");
}

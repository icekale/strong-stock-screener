import { redirect } from "next/navigation";

export default function HeatmapPage() {
  redirect("/market?view=heatmap");
}

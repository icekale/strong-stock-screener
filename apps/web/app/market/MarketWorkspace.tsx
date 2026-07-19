"use client";

import { Segmented } from "antd";
import { useRouter, useSearchParams } from "next/navigation";
import { PageFrame } from "../../components/workbench/PageFrame";
import { normalizeMarketView } from "../../lib/marketWorkspace";
import { HeatmapWorkspaceContent } from "../heatmap/HeatmapWorkspace";
import { SectorPageWorkspaceContent } from "../sectors/SectorPageWorkspace";

const MARKET_VIEW_OPTIONS = [
  { label: "板块", value: "sectors" },
  { label: "热图", value: "heatmap" },
  { label: "ETF资金", value: "etf" },
];

export function MarketWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = normalizeMarketView(searchParams.get("view"));

  function changeView(value: string | number) {
    if (value === "etf") {
      router.push("/etf-radar");
      return;
    }
    const next = normalizeMarketView(value);
    if (next !== view) {
      router.replace("/market?view=" + next, { scroll: false });
    }
  }

  return (
    <PageFrame
      actions={
        <Segmented
          options={MARKET_VIEW_OPTIONS}
          value={view}
          onChange={changeView}
        />
      }
      contentClassName={view === "sectors" ? "market-radar-page-content" : undefined}
      title="板块与热图"
    >
      {view === "heatmap" ? <HeatmapWorkspaceContent /> : <SectorPageWorkspaceContent />}
    </PageFrame>
  );
}

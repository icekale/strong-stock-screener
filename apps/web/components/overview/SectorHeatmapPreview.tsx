import Link from "next/link";
import { DataState } from "../workbench/DataState";
import type { PanelState } from "../../lib/marketOverview";
import type { SectorRadarItem, SectorRadarResponse } from "../../lib/types";

type SectorHeatmapPreviewProps = {
  onRefresh: () => void;
  sectorRadar: PanelState<SectorRadarResponse> | null;
};

export function SectorHeatmapPreview({ onRefresh, sectorRadar }: SectorHeatmapPreviewProps) {
  const data = sectorRadar && sectorRadar.kind !== "error" ? sectorRadar.value : null;

  return (
    <section aria-labelledby="sector-preview-title" className="compact-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="sector-preview-title">
            板块资金流
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">{data ? `${data.flow_source} · ${flowStatusLabel(data.capital_flow_status)}` : "资金流雷达"}</p>
        </div>
        <Link className="text-xs font-medium text-[var(--app-primary)] hover:underline" href="/sectors">
          查看板块
        </Link>
      </div>
      {!data ? <DataState action={{ onClick: onRefresh }} kind={sectorRadar?.kind === "error" ? "error" : "loading"} subject="板块资金流" /> : null}
      {sectorRadar?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="板块资金流" /> : null}
      {data ? (
        <div className="grid divide-y divide-[var(--app-border)] lg:grid-cols-2 lg:divide-x lg:divide-y-0">
          <SectorColumn items={data.inflow} label="净流入" onRefresh={onRefresh} />
          <SectorColumn items={data.outflow} label="净流出" onRefresh={onRefresh} />
        </div>
      ) : null}
    </section>
  );
}

function SectorColumn({ items, label, onRefresh }: { items: SectorRadarItem[]; label: string; onRefresh: () => void }) {
  return (
    <div className="min-w-0">
      <h3 className="border-b border-[var(--app-border)] px-4 py-3 text-sm font-semibold text-[var(--app-ink)]">{label}</h3>
      {items.length === 0 ? <DataState action={{ onClick: onRefresh }} kind="empty" subject={label} /> : null}
      <div className="divide-y divide-[var(--app-border)]">
        {items.slice(0, 4).map((item) => (
          <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3" key={`${label}-${item.name}`}>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-[var(--app-ink)]">{item.name}</div>
              <div className="mt-1 truncate text-xs text-[var(--app-muted)]">领涨：{item.leader ?? "-"}</div>
            </div>
            <div className="text-right text-xs tabular-nums text-[var(--app-muted)]">
              <div className="font-semibold text-[var(--app-ink)]">{formatCny(item.net_flow_cny)}</div>
              <div className="mt-1">{formatPercent(item.change_pct)} · 强度 {item.strength_score.toFixed(1)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function flowStatusLabel(value: SectorRadarResponse["capital_flow_status"]) {
  if (value === "direct") {
    return "直接口径";
  }
  if (value === "estimated") {
    return "估算口径";
  }
  return "不可用";
}

function formatCny(value: number | null) {
  if (value === null) {
    return "-";
  }
  const absolute = Math.abs(value);
  if (absolute >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(1)}亿`;
  }
  if (absolute >= 10_000) {
    return `${(value / 10_000).toFixed(0)}万`;
  }
  return value.toFixed(0);
}

function formatPercent(value: number | null) {
  return value === null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

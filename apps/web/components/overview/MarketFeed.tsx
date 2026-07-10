import Link from "next/link";
import { DataState } from "../workbench/DataState";
import type { PanelState } from "../../lib/marketOverview";
import type { SectorRadarResponse, SentimentSummaryResponse } from "../../lib/types";

type MarketFeedProps = {
  onRefresh: () => void;
  sectorRadar: PanelState<SectorRadarResponse> | null;
  sentiment: PanelState<SentimentSummaryResponse> | null;
};

type FeedRow = {
  detail: string;
  href: "/market?view=sectors" | "/sentiment";
  label: string;
  timestamp: string;
};

export function MarketFeed({ onRefresh, sectorRadar, sentiment }: MarketFeedProps) {
  const radarData = sectorRadar && sectorRadar.kind !== "error" ? sectorRadar.value : null;
  const sentimentData = sentiment && sentiment.kind !== "error" ? sentiment.value : null;
  const rows = buildRows(radarData, sentimentData);
  const initialLoading = sectorRadar === null && sentiment === null;

  return (
    <section aria-labelledby="market-feed-title" className="compact-panel overflow-hidden">
      <div className="compact-panel__header">
        <div>
          <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]" id="market-feed-title">
            市场动态
          </h2>
          <p className="m-0 text-xs text-[var(--app-muted)]">板块资金与情绪快照</p>
        </div>
      </div>
      {initialLoading ? <DataState kind="loading" subject="市场动态" /> : null}
      {sectorRadar?.kind === "error" ? <DataState action={{ onClick: onRefresh }} kind="error" subject="板块资金流" /> : null}
      {sentiment?.kind === "error" ? <DataState action={{ onClick: onRefresh }} kind="error" subject="情绪摘要" /> : null}
      {sectorRadar?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="板块资金流" /> : null}
      {sentiment?.kind === "stale" ? <DataState action={{ onClick: onRefresh }} kind="stale" subject="情绪摘要" /> : null}
      {!initialLoading && rows.length === 0 && sectorRadar?.kind !== "error" && sentiment?.kind !== "error" ? (
        <DataState action={{ onClick: onRefresh }} kind="empty" subject="市场动态" />
      ) : null}
      {rows.length > 0 ? (
        <div className="divide-y divide-[var(--app-border)]">
          {rows.map((row) => (
            <Link
              className="grid grid-cols-[84px_minmax(0,1fr)] gap-3 px-4 py-3 transition-colors hover:bg-[var(--app-raised)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--app-primary)]"
              href={row.href}
              key={`${row.href}-${row.label}-${row.timestamp}`}
            >
              <time className="text-xs tabular-nums text-[var(--app-muted)]" dateTime={row.timestamp}>
                {formatTime(row.timestamp)}
              </time>
              <div className="min-w-0">
                <div className="text-xs font-medium text-[var(--app-ink)]">{row.label}</div>
                <div className="mt-1 truncate text-xs text-[var(--app-muted)]">{row.detail}</div>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function buildRows(sectorRadar: SectorRadarResponse | null, sentiment: SentimentSummaryResponse | null): FeedRow[] {
  const rows: FeedRow[] = [];
  if (sectorRadar?.inflow[0]) {
    rows.push({
      timestamp: sectorRadar.generated_at,
      label: "板块净流入",
      detail: `${sectorRadar.inflow[0].name} ${formatCny(sectorRadar.inflow[0].net_flow_cny)}`,
      href: "/market?view=sectors",
    });
  }
  if (sectorRadar?.outflow[0]) {
    rows.push({
      timestamp: sectorRadar.generated_at,
      label: "板块净流出",
      detail: `${sectorRadar.outflow[0].name} ${formatCny(sectorRadar.outflow[0].net_flow_cny)}`,
      href: "/market?view=sectors",
    });
  }
  if (sentiment) {
    rows.push({
      timestamp: sentiment.cached_at ?? sentiment.generated_at,
      label: "情绪快照",
      detail: `${sentiment.metrics.emotion_level} · 情绪分 ${formatNumber(sentiment.metrics.emotion_score)}`,
      href: "/sentiment",
    });
  }
  return rows.sort((left, right) => right.timestamp.localeCompare(left.timestamp));
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

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Shanghai" });
}

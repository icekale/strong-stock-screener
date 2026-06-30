import type {
  DataSourceStatusResponse,
  GsgfAnalysis,
  MarketOverviewResponse,
  ScreenRunFilters,
  ScreenStrategy,
  SectorRadarItem,
  SectorRadarResponse,
  SourceStatusValue,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistPoolItem,
} from "../../lib/types";
import {
  industryStrengthCopy,
  marketTypeOptions,
  statusCopy,
  strategyOptions,
  type MarketDashboardStats,
  type MarketType,
} from "./types";

export function gsgfLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    strong_candidate: "强势候选",
    watch_candidate: "观察候选",
    wait_trigger: "等触发",
    avoid: "回避",
    a_zone: "A区",
    b_zone_a_point: "B区A点",
    c_zone: "C区",
    unformed: "未成型",
    unknown: "未知",
    capital: "资金",
    confirmation: "确认",
    ma: "均线",
    pattern: "形态",
    risk: "风险",
    safety: "排雷",
    star: "星线",
    trend: "趋势",
    three_yang_controls_three_yin: "三阳控三阴",
    neutral: "量形态中性",
    three_yin_controls_three_yang: "三阴控三阳",
    volume_breakout_confirmation: "放量突破确认",
  };
  return value ? labels[value] ?? value : "--";
}

export function gsgfFinalStatusTone(status: GsgfAnalysis["final_status"]) {
  const tones: Record<GsgfAnalysis["final_status"], string> = {
    候选: "bg-sky-50 text-sky-700 ring-sky-100",
    低吸观察: "market-green-badge ring-1 market-green-ring",
    减仓: "bg-amber-50 text-amber-700 ring-amber-100",
    回避: "bg-red-50 text-red-700 ring-red-100",
    确认买点: "market-green-badge ring-1 market-green-ring",
    观察: "bg-slate-100 text-slate-600 ring-slate-200",
  };
  return tones[status];
}

export function primaryRiskSummary(item: StrongStockScreeningItem) {
  if (item.negative_news_status === "triggered") {
    return {
      text: item.negative_news_flags[0] ?? "负面新闻待核验",
      tone: "font-black text-red-600",
    };
  }
  if (item.severe_abnormal_warning === "triggered") {
    const severeFlag = item.risk_flags.find((flag) => flag.includes("严重异动"));
    return {
      text: severeFlag ?? "严重异动",
      tone: "font-black text-red-600",
    };
  }
  const firstRisk = item.risk_flags.find((flag) => !flag.includes("严重异动"));
  return {
    text: firstRisk ?? "无明显风险",
    tone: firstRisk ? "text-slate-500" : "text-slate-400",
  };
}

export function groupWatchlistPoolItems(items: WatchlistPoolItem[]) {
  const groups: Array<{ name: string; items: WatchlistPoolItem[] }> = [];
  const indexByName = new Map<string, number>();
  for (const item of items) {
    const name = item.group?.trim() || "自选";
    let index = indexByName.get(name);
    if (index === undefined) {
      index = groups.length;
      indexByName.set(name, index);
      groups.push({ name, items: [] });
    }
    groups[index].items.push(item);
  }
  return groups;
}

export function buildMarketDashboardStats(
  items: StrongStockScreeningItem[],
  result: StrongStockScreeningResponse | null,
): MarketDashboardStats {
  return {
    dataIncompleteCount: items.filter((item) => item.status === "data_incomplete").length,
    focusCount: items.filter((item) => item.status === "focus").length,
    negativeNewsCount: items.filter((item) => item.negative_news_status === "triggered").length,
    reduceRiskCount: items.filter((item) => item.status === "reduce_risk").length,
    riskEmptyCount: result?.watchlist_risk_items.filter((item) => item.risk_action === "empty").length ?? 0,
    severeWarningCount: items.filter((item) => item.severe_abnormal_warning === "triggered").length,
    totalCount: items.length,
    waitPullbackCount: items.filter((item) => item.status === "wait_pullback").length,
  };
}

export function sumPositiveSectorFlow(items: SectorRadarItem[]): number {
  return items.reduce((sum, item) => sum + Math.max(0, item.net_flow_cny ?? 0), 0);
}

export function sumNegativeSectorFlow(items: SectorRadarItem[]): number {
  return items.reduce((sum, item) => sum + Math.abs(Math.min(0, item.net_flow_cny ?? 0)), 0);
}

export function formatCnyCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const absValue = Math.abs(value);
  if (absValue >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}万亿`;
  }
  if (absValue >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(0)}亿`;
  }
  if (absValue >= 10_000) {
    return `${(value / 10_000).toFixed(0)}万`;
  }
  return value.toFixed(0);
}

export function formatSignedCny(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatCnyCompact(value)}`;
}

export function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatPlainPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2)}%`;
}

export function formatReviewPercent(value: number | null | undefined): string {
  return formatSignedPercent(value);
}

export function formatTurnoverChange(turnover: MarketOverviewResponse["turnover"] | null): string {
  if (!turnover || turnover.change_cny === null || turnover.change_pct === null) {
    return "昨日对比待确认";
  }
  return `较昨日 ${formatSignedCny(turnover.change_cny)} (${formatSignedPercent(turnover.change_pct)})`;
}

export function marketOverviewSourceSummary(marketOverview: MarketOverviewResponse | null): string {
  const items = marketOverview?.source_status ?? [];
  if (items.length === 0) {
    return "";
  }
  const successCount = items.filter((item) => item.status === "success").length;
  return `${successCount}/${items.length} 市场源可用`;
}

export function sectorRadarSourceSummary(sectorRadar: SectorRadarResponse | null): string {
  const items = sectorRadar?.source_status ?? [];
  if (items.length === 0) {
    return "";
  }
  const successCount = items.filter((item) => item.status === "success").length;
  const flowLabel = sectorRadar?.capital_flow_status === "direct" ? "直接资金流" : "估算资金流";
  return `${successCount}/${items.length} 板块源可用 · ${flowLabel}`;
}

export function realtimeTurnoverSourceLabel(marketOverview: MarketOverviewResponse | null): string | null {
  const statuses = marketOverview?.source_status ?? [];
  if (statuses.some((item) => item.source === "iFinD 实时指数" && item.status === "success")) {
    return "iFinD 实时口径";
  }
  if (statuses.some((item) => item.source === "TickFlow 实时指数" && item.status === "success")) {
    return "TickFlow 实时口径";
  }
  return null;
}

export function sourceSummary(sources: DataSourceStatusResponse | null): { label: string; ok: boolean } {
  if (!sources || sources.items.length === 0) {
    return { label: "读取中", ok: false };
  }
  const successCount = sources.items.filter((item) => item.status === "success").length;
  return {
    label: `${successCount}/${sources.items.length} 可用`,
    ok: successCount === sources.items.length,
  };
}

export function exportCandidatesCsv(items: StrongStockScreeningItem[]) {
  if (typeof window === "undefined" || items.length === 0) {
    return;
  }
  const headers = ["代码", "名称", "行业", "状态", "得分", "板块强度", "风险"];
  const rows = items.map((item) => [
    item.symbol,
    item.name,
    item.industry ?? "",
    statusCopy[item.status].label,
    String(item.score),
    item.industry_strength ? industryStrengthCopy[item.industry_strength].label : "",
    primaryRiskSummary(item).text,
  ]);
  const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `strong-stock-candidates-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string) {
  return `"${value.replaceAll("\"", "\"\"")}"`;
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function strategyName(strategy: ScreenStrategy): string {
  return strategyOptions.find((option) => option.value === strategy)?.label ?? strategy;
}

export function marketTypeLabel(value: MarketType): string {
  return marketTypeOptions.find((option) => option.value === value)?.label ?? value;
}

export function marketCapFilterLabel(filters: ScreenRunFilters): string {
  const min = filters.min_market_cap_billion;
  const max = filters.max_market_cap_billion;
  if (min !== null && min !== undefined && max !== null && max !== undefined) {
    return `市值 ${min}-${max}亿`;
  }
  if (min !== null && min !== undefined) {
    return `市值 > ${min}亿`;
  }
  if (max !== null && max !== undefined) {
    return `市值 < ${max}亿`;
  }
  return "市值不限";
}

export function splitTags(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const tag = chunk.trim();
    if (tag && !seen.has(tag)) {
      seen.add(tag);
      output.push(tag);
    }
  }
  return output;
}

export function splitFilterValues(value: string) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，]/)) {
    const item = chunk.trim();
    if (item && !seen.has(item)) {
      seen.add(item);
      output.push(item);
    }
  }
  return output;
}

export function sourceTagColor(status: SourceStatusValue) {
  const colors: Record<SourceStatusValue, string> = {
    disabled: "default",
    failed: "red",
    missing_key: "orange",
    stale: "blue",
    success: "green",
  };
  return colors[status];
}

export function normalizeOptionalNumber(value: number | string | null, minimum?: number) {
  if (value === null || String(value).trim() === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return minimum === undefined ? parsed : Math.max(minimum, parsed);
}

export function cleanScreenFilters(filters: ScreenRunFilters): ScreenRunFilters {
  return {
    ...(filters.min_market_cap_billion !== null &&
      filters.min_market_cap_billion !== undefined && { min_market_cap_billion: filters.min_market_cap_billion }),
    ...(filters.max_market_cap_billion !== null &&
      filters.max_market_cap_billion !== undefined && { max_market_cap_billion: filters.max_market_cap_billion }),
    ...(filters.kdj_j_max !== null && filters.kdj_j_max !== undefined && { kdj_j_max: filters.kdj_j_max }),
    ...((filters.industries ?? []).length > 0 && { industries: filters.industries }),
    ...((filters.market_types ?? []).length > 0 && { market_types: filters.market_types }),
  };
}

export function activeScreenFilterCount(filters: ScreenRunFilters) {
  let count = 0;
  if (filters.min_market_cap_billion !== null && filters.min_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.max_market_cap_billion !== null && filters.max_market_cap_billion !== undefined) {
    count += 1;
  }
  if (filters.kdj_j_max !== null && filters.kdj_j_max !== undefined) {
    count += 1;
  }
  if ((filters.industries ?? []).length > 0) {
    count += 1;
  }
  if ((filters.market_types ?? []).length > 0) {
    count += 1;
  }
  return count;
}

export function normalizeScanLimit(value: number | string | null) {
  const parsed = typeof value === "number" ? value : Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return 40;
  }
  return Math.max(1, Math.min(300, parsed));
}

export function normalizeKlineCount(value: number | string | null) {
  const parsed = typeof value === "number" ? value : Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) {
    return 260;
  }
  return Math.max(70, Math.min(260, parsed));
}

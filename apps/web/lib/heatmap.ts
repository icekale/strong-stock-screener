import type {
  HeatmapMarketKey,
  HeatmapPeriodKey,
  HeatmapSizeMode,
  HeatmapTrendFilter,
  StrongStockSourceStatus,
} from "./types";

export type HeatmapQueryState = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  sizeMode: HeatmapSizeMode;
  trend: HeatmapTrendFilter;
  board: string;
  limit: number;
};

export const HEATMAP_MARKET_OPTIONS: Array<{ label: string; value: HeatmapMarketKey }> = [
  { label: "全 A", value: "all" },
  { label: "上证 A 股", value: "sse" },
  { label: "深证 A 股", value: "szse" },
  { label: "沪深 300", value: "hs300" },
  { label: "中证 A500", value: "zza500" },
  { label: "创业板", value: "cyb" },
  { label: "科创板", value: "kcb" },
];

export const HEATMAP_PERIOD_OPTIONS: Array<{ label: string; value: HeatmapPeriodKey }> = [
  { label: "日", value: "day" },
  { label: "周", value: "week" },
  { label: "月", value: "month" },
  { label: "年", value: "year" },
];

export const HEATMAP_SIZE_MODE_OPTIONS: Array<{ label: string; value: HeatmapSizeMode }> = [
  { label: "流通市值", value: "market_cap" },
  { label: "成交额", value: "turnover" },
];

export const HEATMAP_TREND_OPTIONS: Array<{ label: string; value: HeatmapTrendFilter }> = [
  { label: "全部", value: "all" },
  { label: "上涨", value: "rise" },
  { label: "下跌", value: "fall" },
];

export function buildHeatmapQuery(state: HeatmapQueryState): URLSearchParams {
  const params = new URLSearchParams({
    market: state.market,
    period: state.period,
    size_mode: state.sizeMode,
    trend: state.trend,
  });
  const board = state.board.trim();
  if (board && board !== "全部") {
    params.set("board", board);
  }
  params.set("limit", String(state.limit));
  return params;
}

export function formatHeatmapMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "-";
  }
  if (Math.abs(value) >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(2)}亿`;
  }
  if (Math.abs(value) >= 10_000) {
    return `${(value / 10_000).toFixed(2)}万`;
  }
  return value.toFixed(0);
}

export function heatmapSourceStatusLabel(status: StrongStockSourceStatus): string {
  if (status.status === "success") {
    return "实时";
  }
  if (status.status === "stale") {
    return "样本/过期";
  }
  if (status.status === "failed") {
    return "失败";
  }
  if (status.status === "disabled") {
    return "未启用";
  }
  return "缺配置";
}

import type {
  ScreenRunFilters,
  ScreenStrategy,
  StrongStockScreeningItem,
} from "../../lib/types";

export const statusCopy: Record<StrongStockScreeningItem["status"], { label: string; tone: string }> = {
  focus: { label: "可关注", tone: "market-green-badge ring-1 market-green-ring" },
  wait_pullback: { label: "等回踩", tone: "bg-sky-50 text-sky-700 ring-sky-100" },
  reduce_risk: { label: "减仓风险", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
  data_incomplete: { label: "数据不足", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

export type CandidateStatusFilter = StrongStockScreeningItem["status"] | "all";

export const candidateStatusFilters: Array<{ label: string; value: CandidateStatusFilter }> = [
  { label: "全部", value: "all" },
  { label: statusCopy.focus.label, value: "focus" },
  { label: statusCopy.wait_pullback.label, value: "wait_pullback" },
  { label: statusCopy.reduce_risk.label, value: "reduce_risk" },
  { label: statusCopy.data_incomplete.label, value: "data_incomplete" },
];

export const strategyOptions: Array<{ label: string; value: ScreenStrategy }> = [
  { label: "强势股模型", value: "strong_stock" },
  { label: "股是股非模型", value: "gsgf" },
  { label: "综合模型", value: "combined" },
];

export const industryStrengthCopy: Record<
  NonNullable<StrongStockScreeningItem["industry_strength"]>,
  { label: string; tone: string }
> = {
  strong: { label: "强", tone: "market-green-badge ring-1 market-green-ring" },
  neutral: { label: "中", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
  weak: { label: "弱", tone: "bg-amber-50 text-amber-700 ring-amber-100" },
};

export type MarketType = NonNullable<ScreenRunFilters["market_types"]>[number];

export const marketTypeOptions: Array<{ label: string; value: MarketType }> = [
  { label: "主板", value: "main" },
  { label: "创业板", value: "gem" },
  { label: "科创板", value: "star" },
  { label: "北交所", value: "bj" },
];

export const realtimeTurnoverSubtitles: Record<string, string> = {
  "iFinD 实时口径": "iFinD 实时口径 · 今日相对昨日",
  "TickFlow 实时口径": "TickFlow 实时口径 · 今日相对昨日",
};

export type MarketDashboardStats = {
  dataIncompleteCount: number;
  focusCount: number;
  negativeNewsCount: number;
  reduceRiskCount: number;
  riskEmptyCount: number;
  severeWarningCount: number;
  totalCount: number;
  waitPullbackCount: number;
};

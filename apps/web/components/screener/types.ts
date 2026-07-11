import type {
  ScreenRunFilters,
  ScreenStrategy,
  StrongStockScreeningItem,
} from "../../lib/types";

export const statusCopy: Record<StrongStockScreeningItem["status"], { label: string; tone: string }> = {
  focus: { label: "可关注", tone: "bg-[var(--app-surface)] text-[var(--app-primary)] ring-[var(--app-border)]" },
  wait_pullback: { label: "等回踩", tone: "bg-[var(--app-raised)] text-[var(--app-muted)] ring-[var(--app-border)]" },
  reduce_risk: { label: "减仓风险", tone: "bg-[var(--market-warning-bg)] text-[var(--market-warning-text)] ring-[var(--market-warning-border)]" },
  data_incomplete: { label: "数据不足", tone: "bg-[var(--app-raised)] text-[var(--app-muted)] ring-[var(--app-border)]" },
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
  strong: { label: "强", tone: "bg-[var(--app-surface)] text-[var(--app-primary)] ring-[var(--app-border)]" },
  neutral: { label: "中", tone: "bg-[var(--app-raised)] text-[var(--app-muted)] ring-[var(--app-border)]" },
  weak: { label: "弱", tone: "bg-[var(--market-warning-bg)] text-[var(--market-warning-text)] ring-[var(--market-warning-border)]" },
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

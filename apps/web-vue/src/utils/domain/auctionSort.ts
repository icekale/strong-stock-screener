import type { AuctionSnapshotItem } from "@/service/types";

export type AuctionSortMode = "score" | "turnover" | "open_gap" | "turnover_rate" | "industry";

export const AUCTION_LOW_TURNOVER_CNY = 30_000_000;

export const AUCTION_SORT_OPTIONS: Array<{ label: string; value: AuctionSortMode }> = [
  { label: "综合强度", value: "score" },
  { label: "成交额优先", value: "turnover" },
  { label: "高开强度", value: "open_gap" },
  { label: "换手优先", value: "turnover_rate" },
  { label: "行业聚集", value: "industry" },
];

export function sortAuctionItems(
  items: readonly AuctionSnapshotItem[],
  mode: AuctionSortMode,
): AuctionSnapshotItem[] {
  const industryStats = buildIndustrySortStats(items);
  return [...items].sort((left, right) => {
    if (mode === "turnover") {
      return byDesc(left.turnover_cny, right.turnover_cny) || byScore(left, right) || bySymbol(left, right);
    }
    if (mode === "open_gap") {
      return byDesc(left.open_gap_pct, right.open_gap_pct) || byScore(left, right) || bySymbol(left, right);
    }
    if (mode === "turnover_rate") {
      return byDesc(left.turnover_rate, right.turnover_rate) || byDesc(left.turnover_cny, right.turnover_cny) || byScore(left, right) || bySymbol(left, right);
    }
    if (mode === "industry") {
      return byIndustryCluster(left, right, industryStats) || byScore(left, right) || bySymbol(left, right);
    }
    return byScore(left, right) || bySymbol(left, right);
  });
}

export function getAuctionSortDescription(mode: AuctionSortMode): string {
  if (mode === "turnover") {
    return "按成交额优先，适合 9:25 后确认盘口可信度。";
  }
  if (mode === "open_gap") {
    return "按高开强度优先，适合快速定位最主动的竞价票。";
  }
  if (mode === "turnover_rate") {
    return "按换手优先，适合找弹性更强、资金参与度更高的候选。";
  }
  if (mode === "industry") {
    return "按行业聚集优先，适合先看早盘主线是否成团。";
  }
  return "按竞价模型综合排序，成交额作为可信度权重而不是唯一标准。";
}

export function getAuctionLiquidityWarning(item: AuctionSnapshotItem): string | null {
  if (item.turnover_cny === null) {
    return "成交额待确认";
  }
  if (item.turnover_cny < AUCTION_LOW_TURNOVER_CNY) {
    return "成交额不足";
  }
  return null;
}

function buildIndustrySortStats(items: readonly AuctionSnapshotItem[]): Map<string, { count: number; strongCount: number; turnoverCny: number }> {
  const stats = new Map<string, { count: number; strongCount: number; turnoverCny: number }>();
  for (const item of items) {
    const industry = item.industry || "未标注";
    const current = stats.get(industry) ?? { count: 0, strongCount: 0, turnoverCny: 0 };
    current.count += 1;
    current.turnoverCny += item.turnover_cny ?? 0;
    if ((item.open_gap_pct ?? -999) >= 3 || item.tier === "strong_high_open") {
      current.strongCount += 1;
    }
    stats.set(industry, current);
  }
  return stats;
}

function byIndustryCluster(
  left: AuctionSnapshotItem,
  right: AuctionSnapshotItem,
  stats: Map<string, { count: number; strongCount: number; turnoverCny: number }>,
): number {
  const leftStats = stats.get(left.industry || "未标注");
  const rightStats = stats.get(right.industry || "未标注");
  return (
    byDesc(leftStats?.count ?? 0, rightStats?.count ?? 0) ||
    byDesc(leftStats?.strongCount ?? 0, rightStats?.strongCount ?? 0) ||
    byDesc(leftStats?.turnoverCny ?? 0, rightStats?.turnoverCny ?? 0)
  );
}

function byScore(left: AuctionSnapshotItem, right: AuctionSnapshotItem): number {
  return (
    byDesc(left.auction_score, right.auction_score) ||
    byDesc(left.open_gap_pct, right.open_gap_pct) ||
    byDesc(left.current_pct_change, right.current_pct_change) ||
    byDesc(left.turnover_cny, right.turnover_cny) ||
    byDesc(left.turnover_rate, right.turnover_rate)
  );
}

function byDesc(left: number | null | undefined, right: number | null | undefined): number {
  return (right ?? -Infinity) - (left ?? -Infinity);
}

function bySymbol(left: AuctionSnapshotItem, right: AuctionSnapshotItem): number {
  return left.symbol.localeCompare(right.symbol);
}

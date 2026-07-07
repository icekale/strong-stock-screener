import type { HeatmapBoardNode, HeatmapStockNode, StrongStockSourceStatus } from "../../lib/types";

export function buildHeatmapBoardOptions(
  nodes: HeatmapBoardNode[],
): Array<{ label: string; value: string }> {
  const counts = new Map<string, number>();

  for (const node of nodes) {
    const name = node.name.trim();
    if (!name) {
      continue;
    }
    counts.set(name, (counts.get(name) ?? 0) + node.stock_count);
  }

  return [
    { label: "全部", value: "全部" },
    ...Array.from(counts.entries())
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], "zh-CN"))
      .map(([name, count]) => ({ label: `${name} ${count}`, value: name })),
  ];
}

export function resolveHeatmapDisplayStock(
  selectedStock: HeatmapStockNode | null,
  hoverStock: HeatmapStockNode | null,
): HeatmapStockNode | null {
  return selectedStock ?? hoverStock;
}

export function heatmapSourceSummaryLabel(statuses: ReadonlyArray<Pick<StrongStockSourceStatus, "status">>): string {
  const hasSuccess = statuses.some((item) => item.status === "success");
  const hasStale = statuses.some((item) => item.status === "stale");
  const hasFailed = statuses.some((item) => item.status === "failed");

  if (hasStale) {
    return "样本数据";
  }
  if (hasSuccess && hasFailed) {
    return "部分实时";
  }
  if (hasFailed) {
    return "数据源失败";
  }
  if (hasSuccess) {
    return "实时数据";
  }
  return "状态未知";
}

export function heatmapSourceSummaryTone(
  statuses: ReadonlyArray<Pick<StrongStockSourceStatus, "status">>,
): "success" | "warning" | "error" | "default" {
  const hasSuccess = statuses.some((item) => item.status === "success");
  const hasStale = statuses.some((item) => item.status === "stale");
  const hasFailed = statuses.some((item) => item.status === "failed");

  if (hasStale || (hasSuccess && hasFailed)) {
    return "warning";
  }
  if (hasFailed) {
    return "error";
  }
  if (hasSuccess) {
    return "success";
  }
  return "default";
}

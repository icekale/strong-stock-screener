import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";

export type HeatmapViewport = { scale: number; offsetX: number; offsetY: number };
export type HeatmapRect = { x: number; y: number; width: number; height: number };
export type HeatmapBoardRect = HeatmapRect & { board: HeatmapBoardNode };
export type HeatmapStockRect = HeatmapRect & { board: HeatmapBoardNode; stock: HeatmapStockNode };
export type HeatmapLayout = { boards: HeatmapBoardRect[]; stocks: HeatmapStockRect[] };
export type HeatmapChangeColor = { tone: "rise" | "fall" | "flat"; fill: string; text: string };

type WeightedEntry<T> = { item: T; value: number };

export function layoutHeatmapTreemap(
  nodes: HeatmapBoardNode[],
  size: { width: number; height: number },
): HeatmapLayout {
  const rootRect = {
    x: 0,
    y: 0,
    width: finiteDimension(size.width),
    height: finiteDimension(size.height),
  };
  const boards: HeatmapBoardRect[] = [];
  const stocks: HeatmapStockRect[] = [];
  const boardSlices = sliceDice(
    nodes.map((board) => ({ item: board, value: board.value })),
    rootRect,
    "horizontal",
  );

  for (const boardSlice of boardSlices) {
    const boardRect = { ...boardSlice.rect, board: boardSlice.item };
    boards.push(boardRect);

    const stockRect = insetRect(boardSlice.rect, 6);
    const stockSlices = sliceDice(
      boardSlice.item.children.map((stock) => ({ item: stock, value: stock.value })),
      stockRect,
      "vertical",
    );
    for (const stockSlice of stockSlices) {
      stocks.push({ ...stockSlice.rect, board: boardSlice.item, stock: stockSlice.item });
    }
  }

  return { boards, stocks };
}

export function heatmapChangeColor(changePct: number): HeatmapChangeColor {
  if (!Number.isFinite(changePct) || Math.abs(changePct) <= 0.1) {
    return { tone: "flat", fill: "#4b5563", text: "#ffffff" };
  }
  if (changePct > 0) {
    return { tone: "rise", fill: riseColor(changePct), text: "#ffffff" };
  }
  return { tone: "fall", fill: fallColor(changePct), text: "#ffffff" };
}

export function hitTestHeatmap(stocks: HeatmapStockRect[], point: { x: number; y: number }): HeatmapStockRect | null {
  for (let index = stocks.length - 1; index >= 0; index -= 1) {
    const stock = stocks[index];
    if (
      point.x >= stock.x &&
      point.x <= stock.x + stock.width &&
      point.y >= stock.y &&
      point.y <= stock.y + stock.height
    ) {
      return stock;
    }
  }
  return null;
}

export function transformHeatmapPoint(point: { x: number; y: number }, viewport: HeatmapViewport): { x: number; y: number } {
  const scale = Number.isFinite(viewport.scale) && viewport.scale !== 0 ? viewport.scale : 1;
  const offsetX = Number.isFinite(viewport.offsetX) ? viewport.offsetX : 0;
  const offsetY = Number.isFinite(viewport.offsetY) ? viewport.offsetY : 0;
  return {
    x: (point.x - offsetX) / scale,
    y: (point.y - offsetY) / scale,
  };
}

function sliceDice<T>(
  entries: Array<WeightedEntry<T>>,
  rect: HeatmapRect,
  direction: "horizontal" | "vertical",
): Array<{ item: T; rect: HeatmapRect }> {
  if (entries.length === 0) {
    return [];
  }

  const weights = entries.map((entry) => Math.max(1, finiteNumber(entry.value)));
  const total = weights.reduce((sum, value) => sum + value, 0);
  let cursor = direction === "horizontal" ? rect.x : rect.y;

  return entries.map((entry, index) => {
    const isLast = index === entries.length - 1;
    const available = direction === "horizontal" ? rect.x + rect.width - cursor : rect.y + rect.height - cursor;
    const length = isLast ? available : ((direction === "horizontal" ? rect.width : rect.height) * weights[index]) / total;
    const safeLength = Math.max(0, finiteNumber(length));
    const childRect =
      direction === "horizontal"
        ? { x: cursor, y: rect.y, width: safeLength, height: rect.height }
        : { x: rect.x, y: cursor, width: rect.width, height: safeLength };
    cursor += safeLength;
    return { item: entry.item, rect: childRect };
  });
}

function insetRect(rect: HeatmapRect, padding: number): HeatmapRect {
  const safePadding = Math.max(0, Math.min(padding, rect.width / 2 - 0.5, rect.height / 2 - 0.5));
  if (safePadding <= 0) {
    return rect;
  }
  return {
    x: rect.x + safePadding,
    y: rect.y + safePadding,
    width: rect.width - safePadding * 2,
    height: rect.height - safePadding * 2,
  };
}

function riseColor(changePct: number): string {
  if (changePct >= 5) {
    return "#b91c1c";
  }
  if (changePct >= 2) {
    return "#dc2626";
  }
  return "#ef4444";
}

function fallColor(changePct: number): string {
  if (changePct <= -5) {
    return "#047857";
  }
  if (changePct <= -2) {
    return "#059669";
  }
  return "#10b981";
}

function finiteDimension(value: number): number {
  return Math.max(0, finiteNumber(value));
}

function finiteNumber(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

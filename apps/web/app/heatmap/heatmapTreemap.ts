import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";

export type HeatmapViewport = { scale: number; offsetX: number; offsetY: number };
export type HeatmapRect = { x: number; y: number; width: number; height: number };
export type HeatmapBoardRect = HeatmapRect & {
  board: HeatmapBoardNode;
  titleHeight: number;
  changePct: number;
};
export type HeatmapSubBoardRect = HeatmapRect & {
  board: HeatmapBoardNode;
  name: string;
  titleHeight: number;
  stockCount: number;
  changePct: number;
};
export type HeatmapStockRect = HeatmapRect & {
  board: HeatmapBoardNode;
  subBoard: HeatmapSubBoardRect | null;
  stock: HeatmapStockNode;
};
export type HeatmapLayout = {
  boards: HeatmapBoardRect[];
  subBoards: HeatmapSubBoardRect[];
  stocks: HeatmapStockRect[];
};
export type HeatmapChangeColor = { tone: "rise" | "fall" | "flat"; fill: string; text: string };

type WeightedEntry<T> = { item: T; value: number };
type TreemapRect<T> = HeatmapRect & { item: T };

const BOARD_GAP = 4;
const SUB_BOARD_GAP = 3;
const STOCK_GAP = 1.4;
const BOARD_TITLE_HEIGHT = 24;
const SUB_BOARD_TITLE_HEIGHT = 17;
const FLAT_THRESHOLD = 0.1;

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
  const subBoards: HeatmapSubBoardRect[] = [];
  const stocks: HeatmapStockRect[] = [];
  const boardRects = binaryTreemap(
    nodes.map((board) => ({ item: board, value: board.value })),
    rootRect.x,
    rootRect.y,
    rootRect.width,
    rootRect.height,
    BOARD_GAP,
  );

  for (const boardRect of boardRects) {
    const board = boardRect.item;
    const titleHeight = boardRect.width >= 80 && boardRect.height >= 42 ? Math.min(BOARD_TITLE_HEIGHT, boardRect.height * 0.2) : 0;
    const renderedBoard: HeatmapBoardRect = {
      ...withoutItem(boardRect),
      board,
      titleHeight,
      changePct: finiteNumber(board.avg_change_pct ?? 0),
    };
    boards.push(renderedBoard);

    const boardContent = insetRect(
      {
        x: boardRect.x,
        y: boardRect.y + titleHeight,
        width: boardRect.width,
        height: Math.max(0, boardRect.height - titleHeight),
      },
      4,
    );
    const grouped = groupStocksBySubIndustry(board);
    const subBoardRects = binaryTreemap(
      grouped.map((group) => ({ item: group, value: group.value })),
      boardContent.x,
      boardContent.y,
      boardContent.width,
      boardContent.height,
      SUB_BOARD_GAP,
    );

    for (const subBoardRect of subBoardRects) {
      const titleHeight =
        subBoardRect.width >= 58 && subBoardRect.height >= 38
          ? Math.min(SUB_BOARD_TITLE_HEIGHT, subBoardRect.height * 0.24)
          : 0;
      const renderedSubBoard: HeatmapSubBoardRect = {
        ...withoutItem(subBoardRect),
        board,
        name: subBoardRect.item.name,
        stockCount: subBoardRect.item.children.length,
        titleHeight,
        changePct: subBoardRect.item.changePct,
      };
      subBoards.push(renderedSubBoard);

      const stockArea = insetRect(
        {
          x: subBoardRect.x,
          y: subBoardRect.y + titleHeight,
          width: subBoardRect.width,
          height: Math.max(0, subBoardRect.height - titleHeight),
        },
        2,
      );
      const stockRects = binaryTreemap(
        subBoardRect.item.children.map((stock) => ({ item: stock, value: stock.value })),
        stockArea.x,
        stockArea.y,
        stockArea.width,
        stockArea.height,
        STOCK_GAP,
      );

      for (const stockRect of stockRects) {
        stocks.push({
          ...withoutItem(stockRect),
          board,
          subBoard: renderedSubBoard,
          stock: stockRect.item,
        });
      }
    }
  }

  return { boards, subBoards, stocks };
}

export function heatmapChangeColor(changePct: number): HeatmapChangeColor {
  if (!Number.isFinite(changePct) || Math.abs(changePct) <= FLAT_THRESHOLD) {
    return { tone: "flat", fill: "rgb(72, 79, 92)", text: "#f8fafc" };
  }

  const amplitude = clamp(Math.abs(changePct) / 10, 0, 1);
  if (changePct > 0) {
    const red = Math.round(140 + amplitude * 115);
    const green = Math.round(72 - amplitude * 42);
    const blue = Math.round(76 - amplitude * 38);
    return { tone: "rise", fill: `rgb(${red}, ${green}, ${blue})`, text: "#f8fafc" };
  }

  const red = Math.round(40 - amplitude * 14);
  const green = Math.round(126 + amplitude * 88);
  const blue = Math.round(76 - amplitude * 10);
  return { tone: "fall", fill: `rgb(${red}, ${green}, ${blue})`, text: "#f8fafc" };
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

function groupStocksBySubIndustry(board: HeatmapBoardNode) {
  const groups = new Map<string, HeatmapStockNode[]>();
  for (const stock of board.children) {
    const key = stock.sub_industry?.trim() || stock.industry || board.name;
    const items = groups.get(key) ?? [];
    items.push(stock);
    groups.set(key, items);
  }

  return Array.from(groups.entries())
    .map(([name, children]) => ({
      name,
      children: [...children].sort((left, right) => right.value - left.value),
      value: children.reduce((sum, child) => sum + normalizeSizeValue(child.value), 0),
      changePct: weightedAverageChange(children),
    }))
    .sort((left, right) => right.value - left.value);
}

function weightedAverageChange(stocks: HeatmapStockNode[]): number {
  let weightedSum = 0;
  let totalValue = 0;
  for (const stock of stocks) {
    const value = normalizeSizeValue(stock.value);
    weightedSum += finiteNumber(stock.change_pct) * value;
    totalValue += value;
  }
  return totalValue > 0 ? weightedSum / totalValue : 0;
}

function binaryTreemap<T>(
  entries: Array<WeightedEntry<T>>,
  x: number,
  y: number,
  width: number,
  height: number,
  gap = 0,
): Array<TreemapRect<T>> {
  const sortedEntries = entries
    .map((entry) => ({ item: entry.item, value: normalizeSizeValue(entry.value) }))
    .filter((entry) => entry.value > 0)
    .sort((left, right) => right.value - left.value);

  function layout(items: Array<WeightedEntry<T>>, bounds: HeatmapRect): Array<TreemapRect<T>> {
    if (items.length === 0 || bounds.width <= 1 || bounds.height <= 1) {
      return [];
    }
    if (items.length === 1) {
      return [insetTreemapRect({ ...bounds, item: items[0].item }, gap)];
    }

    const splitIndex = findBalancedSplitIndex(items);
    const firstItems = items.slice(0, splitIndex);
    const secondItems = items.slice(splitIndex);
    if (firstItems.length === 0 || secondItems.length === 0) {
      return items.map((entry, index) =>
        insetTreemapRect(
          {
            item: entry.item,
            x: bounds.x,
            y: bounds.y + (bounds.height / items.length) * index,
            width: bounds.width,
            height: bounds.height / items.length,
          },
          gap,
        ),
      );
    }

    const total = totalTreemapValue(items);
    const ratio = totalTreemapValue(firstItems) / total;
    const { first, second } = splitBounds(bounds, ratio);
    return [...layout(firstItems, first), ...layout(secondItems, second)];
  }

  return layout(sortedEntries, {
    x: finiteNumber(x),
    y: finiteNumber(y),
    width: finiteDimension(width),
    height: finiteDimension(height),
  }).filter((rect) => rect.width > 1 && rect.height > 1);
}

function findBalancedSplitIndex<T>(entries: Array<WeightedEntry<T>>): number {
  if (entries.length <= 1) {
    return entries.length;
  }

  const target = totalTreemapValue(entries) / 2;
  let cumulative = 0;
  let bestIndex = 1;
  let bestDiff = Number.POSITIVE_INFINITY;

  for (let index = 1; index < entries.length; index += 1) {
    cumulative += entries[index - 1].value;
    const diff = Math.abs(target - cumulative);
    if (diff < bestDiff) {
      bestDiff = diff;
      bestIndex = index;
    }
  }
  return bestIndex;
}

function splitBounds(bounds: HeatmapRect, ratio: number): { first: HeatmapRect; second: HeatmapRect } {
  const safeRatio = clamp(ratio, 0, 1);
  if (bounds.width >= bounds.height) {
    const firstWidth = bounds.width * safeRatio;
    return {
      first: { x: bounds.x, y: bounds.y, width: firstWidth, height: bounds.height },
      second: {
        x: bounds.x + firstWidth,
        y: bounds.y,
        width: Math.max(0, bounds.width - firstWidth),
        height: bounds.height,
      },
    };
  }

  const firstHeight = bounds.height * safeRatio;
  return {
    first: { x: bounds.x, y: bounds.y, width: bounds.width, height: firstHeight },
    second: {
      x: bounds.x,
      y: bounds.y + firstHeight,
      width: bounds.width,
      height: Math.max(0, bounds.height - firstHeight),
    },
  };
}

function insetTreemapRect<T>(rect: TreemapRect<T>, gap: number): TreemapRect<T> {
  const inset = Math.max(0, gap / 2);
  return {
    ...rect,
    x: rect.x + inset,
    y: rect.y + inset,
    width: Math.max(0, rect.width - gap),
    height: Math.max(0, rect.height - gap),
  };
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

function withoutItem<T>(rect: TreemapRect<T>): HeatmapRect {
  return {
    x: rect.x,
    y: rect.y,
    width: rect.width,
    height: rect.height,
  };
}

function totalTreemapValue<T>(entries: Array<WeightedEntry<T>>): number {
  return entries.reduce((sum, entry) => sum + normalizeSizeValue(entry.value), 0);
}

function normalizeSizeValue(value: number): number {
  return Number.isFinite(value) && value > 1 ? value : 1;
}

function finiteDimension(value: number): number {
  return Math.max(0, finiteNumber(value));
}

function finiteNumber(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

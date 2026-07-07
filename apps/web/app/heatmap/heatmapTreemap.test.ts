import assert from "node:assert/strict";
import test from "node:test";
import type { HeatmapBoardNode } from "../../lib/types";

const {
  heatmapChangeColor,
  hitTestHeatmap,
  layoutHeatmapTreemap,
  transformHeatmapPoint,
} = (await import(new URL("./heatmapTreemap.ts", import.meta.url).href)) as typeof import("./heatmapTreemap");

const nodes = [
  {
    key: "半导体",
    name: "半导体",
    value: 120,
    stock_count: 2,
    advance_count: 1,
    decline_count: 1,
    unchanged_count: 0,
    avg_change_pct: 0.8,
    turnover_cny: 100,
    children: [
      {
        symbol: "603690.SH",
        code: "603690",
        name: "至纯科技",
        industry: "半导体",
        sub_industry: "半导体设备",
        exchange: "SH",
        market: "sse",
        price: 28,
        change_pct: 3.2,
        week_change_pct: null,
        month_change_pct: null,
        year_change_pct: null,
        turnover_cny: 80,
        circulating_market_cap_cny: 100,
        total_market_cap_cny: 120,
        value: 80,
        quote_time: null,
      },
      {
        symbol: "300475.SZ",
        code: "300475",
        name: "香农芯创",
        industry: "半导体",
        sub_industry: "存储芯片",
        exchange: "SZ",
        market: "cyb",
        price: 54,
        change_pct: -1.8,
        week_change_pct: null,
        month_change_pct: null,
        year_change_pct: null,
        turnover_cny: 40,
        circulating_market_cap_cny: 60,
        total_market_cap_cny: 80,
        value: 40,
        quote_time: null,
      },
    ],
  },
] satisfies HeatmapBoardNode[];

test("layoutHeatmapTreemap produces bounded board and stock rectangles", () => {
  const layout = layoutHeatmapTreemap(nodes, { width: 1000, height: 600 });

  assert.equal(layout.boards.length, 1);
  assert.equal(layout.stocks.length, 2);
  for (const item of [...layout.boards, ...layout.stocks]) {
    assert.ok(item.x >= 0);
    assert.ok(item.y >= 0);
    assert.ok(item.x + item.width <= 1000);
    assert.ok(item.y + item.height <= 600);
    assert.ok(item.width > 0);
    assert.ok(item.height > 0);
  }
});

test("layoutHeatmapTreemap keeps tiny stocks renderable without NaN", () => {
  const tinyLayout = layoutHeatmapTreemap(
    [
      {
        ...nodes[0],
        value: 1,
        children: nodes[0].children.map((stock, index) => ({
          ...stock,
          value: index === 0 ? 0 : 0.0001,
        })),
      },
    ],
    { width: 320, height: 220 },
  );

  assert.equal(tinyLayout.stocks.length, 2);
  assert.ok(tinyLayout.stocks.every((item) => Number.isFinite(item.width) && Number.isFinite(item.height)));
});

test("heatmapChangeColor follows A-share red-rise and green-fall convention", () => {
  assert.equal(heatmapChangeColor(4).tone, "rise");
  assert.equal(heatmapChangeColor(-2).tone, "fall");
  assert.equal(heatmapChangeColor(0.02).tone, "flat");
});

test("hitTestHeatmap returns topmost stock under transformed pointer", () => {
  const layout = layoutHeatmapTreemap(nodes, { width: 1000, height: 600 });
  const first = layout.stocks[0];
  const point = transformHeatmapPoint(
    { x: first.x + first.width / 2, y: first.y + first.height / 2 },
    { scale: 1, offsetX: 0, offsetY: 0 },
  );

  assert.equal(hitTestHeatmap(layout.stocks, point)?.stock.symbol, first.stock.symbol);
});

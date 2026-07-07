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

test("layoutHeatmapTreemap uses balanced binary subdivision instead of one-dimensional stripes", () => {
  const layout = layoutHeatmapTreemap(
    [
      {
        ...nodes[0],
        children: [
          { ...nodes[0].children[0], symbol: "000001.SZ", code: "000001", name: "平安银行", value: 55 },
          { ...nodes[0].children[1], symbol: "000002.SZ", code: "000002", name: "万科A", value: 45 },
          { ...nodes[0].children[0], symbol: "000063.SZ", code: "000063", name: "中兴通讯", value: 35 },
          { ...nodes[0].children[1], symbol: "000333.SZ", code: "000333", name: "美的集团", value: 25 },
        ],
      },
    ],
    { width: 640, height: 360 },
  );

  assert.equal(layout.stocks.length, 4);
  assert.ok(layout.stocks.some((stock) => stock.width < 300));
  assert.ok(layout.stocks.some((stock) => stock.height < 160));
});

test("layoutHeatmapTreemap groups stocks by sub-industry before drawing stock cells", () => {
  const layout = layoutHeatmapTreemap(
    [
      {
        ...nodes[0],
        children: [
          { ...nodes[0].children[0], symbol: "603690.SH", code: "603690", name: "至纯科技", sub_industry: "半导体设备", value: 60 },
          { ...nodes[0].children[1], symbol: "300475.SZ", code: "300475", name: "香农芯创", sub_industry: "存储芯片", value: 40 },
          { ...nodes[0].children[0], symbol: "688981.SH", code: "688981", name: "中芯国际", sub_industry: "晶圆制造", value: 30 },
        ],
      },
    ],
    { width: 720, height: 420 },
  );

  assert.deepEqual(
    layout.subBoards.map((item) => item.name).sort(),
    ["半导体设备", "存储芯片", "晶圆制造"],
  );
  assert.equal(layout.subBoards.every((item) => item.board.name === "半导体"), true);
  assert.equal(layout.stocks.every((item) => item.subBoard !== null), true);
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
  for (const item of tinyLayout.stocks) {
    assert.ok(Number.isFinite(item.x));
    assert.ok(Number.isFinite(item.y));
    assert.ok(Number.isFinite(item.width));
    assert.ok(Number.isFinite(item.height));
    assert.ok(item.x >= 0);
    assert.ok(item.y >= 0);
    assert.ok(item.x + item.width <= 320);
    assert.ok(item.y + item.height <= 220);
    assert.ok(item.width > 0);
    assert.ok(item.height > 0);
  }
});

test("heatmapChangeColor follows A-share red-rise and green-fall convention", () => {
  assert.equal(heatmapChangeColor(4).tone, "rise");
  assert.equal(heatmapChangeColor(-2).tone, "fall");
  assert.equal(heatmapChangeColor(0.02).tone, "flat");
  assert.equal(heatmapChangeColor(0.1).tone, "flat");
  assert.equal(heatmapChangeColor(-0.1).tone, "flat");
});

test("hitTestHeatmap returns topmost stock under transformed pointer", () => {
  const topmost = nodes[0].children[1];
  const overlappingStocks = [
    { x: 30, y: 40, width: 100, height: 80, board: nodes[0], subBoard: null, stock: nodes[0].children[0] },
    { x: 30, y: 40, width: 100, height: 80, board: nodes[0], subBoard: null, stock: topmost },
  ];
  const point = transformHeatmapPoint(
    { x: 110, y: 120 },
    { scale: 2, offsetX: 10, offsetY: 20 },
  );

  assert.equal(hitTestHeatmap(overlappingStocks, point)?.stock.symbol, topmost.symbol);
});

test("transformHeatmapPoint ignores non-finite offsets", () => {
  assert.deepEqual(
    transformHeatmapPoint(
      { x: 50, y: 80 },
      { scale: 2, offsetX: Number.NaN, offsetY: Number.POSITIVE_INFINITY },
    ),
    { x: 25, y: 40 },
  );
});

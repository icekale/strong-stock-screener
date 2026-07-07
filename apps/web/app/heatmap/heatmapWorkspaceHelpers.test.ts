import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { HeatmapBoardNode, HeatmapStockNode } from "../../lib/types";

const {
  buildHeatmapBoardOptions,
  heatmapSourceSummaryLabel,
  heatmapSourceSummaryTone,
  resolveHeatmapDisplayStock,
} = (await import(new URL("./heatmapWorkspaceHelpers.ts", import.meta.url).href)) as typeof import("./heatmapWorkspaceHelpers");

const stockA = {
  symbol: "603690.SH",
  code: "603690",
  name: "至纯科技",
  industry: "半导体",
  sub_industry: "半导体设备",
  exchange: "SH",
  market: "sse",
  price: 28.4,
  change_pct: 3.2,
  week_change_pct: 8.1,
  month_change_pct: 12.4,
  year_change_pct: 30.5,
  turnover_cny: 120_000_000,
  circulating_market_cap_cny: 12_000_000_000,
  total_market_cap_cny: 15_000_000_000,
  value: 12_000_000_000,
  quote_time: "2026-07-07T10:30:00+08:00",
} satisfies HeatmapStockNode;

const stockB = {
  ...stockA,
  symbol: "300475.SZ",
  code: "300475",
  name: "香农芯创",
  industry: "半导体",
  market: "cyb",
  change_pct: -1.2,
} satisfies HeatmapStockNode;

const boards = [
  {
    key: "半导体",
    name: "半导体",
    value: 100,
    stock_count: 2,
    advance_count: 1,
    decline_count: 1,
    unchanged_count: 0,
    avg_change_pct: 1,
    turnover_cny: 100,
    children: [stockA, stockB],
  },
  {
    key: "机器人",
    name: "机器人",
    value: 80,
    stock_count: 0,
    advance_count: 0,
    decline_count: 0,
    unchanged_count: 0,
    avg_change_pct: null,
    turnover_cny: null,
    children: [],
  },
  {
    key: "半导体-repeat",
    name: "半导体",
    value: 20,
    stock_count: 1,
    advance_count: 1,
    decline_count: 0,
    unchanged_count: 0,
    avg_change_pct: 3.2,
    turnover_cny: 20,
    children: [stockA],
  },
] satisfies HeatmapBoardNode[];

test("buildHeatmapBoardOptions keeps all option and deduplicates board names", () => {
  assert.deepEqual(buildHeatmapBoardOptions(boards), [
    { label: "全部", value: "全部" },
    { label: "半导体 3", value: "半导体" },
    { label: "机器人 0", value: "机器人" },
  ]);
});

test("resolveHeatmapDisplayStock prefers selected stock over hover stock", () => {
  assert.equal(resolveHeatmapDisplayStock(stockA, stockB)?.symbol, "603690.SH");
  assert.equal(resolveHeatmapDisplayStock(null, stockB)?.symbol, "300475.SZ");
  assert.equal(resolveHeatmapDisplayStock(null, null), null);
});

test("heatmap source summary does not hide fallback behind partial success", () => {
  const staleStatuses = [
    { source: "东方财富热图行情", status: "stale", detail: "使用样本" },
    { source: "同花顺市场概览", status: "success", detail: "实时" },
  ] as const;
  const ancillaryFailureStatuses = [
    { source: "东方财富热图行情", status: "success", detail: "实时行情" },
    { source: "东方财富热图摘要", status: "failed", detail: "使用节点聚合摘要" },
  ] as const;

  assert.equal(heatmapSourceSummaryLabel(staleStatuses), "样本数据");
  assert.equal(heatmapSourceSummaryTone(staleStatuses), "warning");
  assert.equal(heatmapSourceSummaryLabel(ancillaryFailureStatuses), "部分实时");
  assert.equal(heatmapSourceSummaryTone(ancillaryFailureStatuses), "warning");
});

test("heatmap K-line action uses a direct href button without nested interactive elements", () => {
  const source = readFileSync(new URL("./HeatmapWorkspace.tsx", import.meta.url), "utf-8");

  assert.ok(source.includes('<Button block href={heatmapStockHref(displayStock)} type="primary">'));
  assert.equal(source.includes('import Link from "next/link"'), false);
});

test("heatmap alerts use Ant Design title prop instead of deprecated message prop", () => {
  const source = readFileSync(new URL("./HeatmapWorkspace.tsx", import.meta.url), "utf-8");

  assert.equal(source.includes("<Alert className=\"mb-4\" message={error}"), false);
  assert.ok(source.includes("<Alert className=\"mb-4\" title={error}"));
});

import assert from "node:assert/strict";
import test from "node:test";

const {
  buildHeatmapQuery,
  formatHeatmapMoney,
  HEATMAP_SIZE_MODE_OPTIONS,
  heatmapSourceStatusLabel,
} = (await import(new URL("./heatmap.ts", import.meta.url).href)) as typeof import("./heatmap");

test("heatmap query maps filters to backend params", () => {
  assert.equal(
    buildHeatmapQuery({
      market: "sse",
      period: "week",
      sizeMode: "turnover",
      trend: "rise",
      board: "半导体",
      limit: 800,
    }).toString(),
    "market=sse&period=week&size_mode=turnover&trend=rise&board=%E5%8D%8A%E5%AF%BC%E4%BD%93&limit=800",
  );
});

test("heatmap query omits all-board and blank board filters", () => {
  const baseQuery = {
    market: "all",
    period: "day",
    sizeMode: "market_cap",
    trend: "all",
    limit: 500,
  } as const;

  assert.equal(buildHeatmapQuery({ ...baseQuery, board: "全部" }).has("board"), false);
  assert.equal(buildHeatmapQuery({ ...baseQuery, board: "   " }).has("board"), false);
});

test("heatmap size mode options cover market cap and turnover", () => {
  assert.deepEqual(HEATMAP_SIZE_MODE_OPTIONS, [
    { label: "流通市值", value: "market_cap" },
    { label: "成交额", value: "turnover" },
  ]);
});

test("heatmap money formatter keeps trading-scale units compact", () => {
  assert.equal(formatHeatmapMoney(123_000_000), "1.23亿");
  assert.equal(formatHeatmapMoney(12_300), "1.23万");
  assert.equal(formatHeatmapMoney(null), "-");
});

test("heatmap source status labels make fallback explicit", () => {
  assert.equal(heatmapSourceStatusLabel({ source: "热图内置样本", status: "stale", detail: "sample" }), "样本/过期");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "success", detail: "ok" }), "实时");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "failed", detail: "error" }), "失败");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "disabled", detail: "off" }), "未启用");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "missing_key", detail: "key" }), "缺配置");
});

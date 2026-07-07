import assert from "node:assert/strict";
import test from "node:test";

const {
  buildHeatmapQuery,
  formatHeatmapMoney,
  heatmapSourceStatusLabel,
  heatmapStockHref,
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

test("heatmap money formatter keeps trading-scale units compact", () => {
  assert.equal(formatHeatmapMoney(123_000_000), "1.23亿");
  assert.equal(formatHeatmapMoney(12_300), "1.23万");
  assert.equal(formatHeatmapMoney(null), "-");
});

test("heatmap source status labels make fallback explicit", () => {
  assert.equal(heatmapSourceStatusLabel({ source: "热图内置样本", status: "stale", detail: "sample" }), "样本/过期");
  assert.equal(heatmapSourceStatusLabel({ source: "东方财富热图行情", status: "success", detail: "ok" }), "实时");
});

test("heatmap stock href returns to heatmap workbench", () => {
  assert.equal(
    heatmapStockHref({ symbol: "603690.SH", name: "至纯科技", industry: "半导体" }),
    "/stock/603690.SH?from=heatmap&name=%E8%87%B3%E7%BA%AF%E7%A7%91%E6%8A%80&industry=%E5%8D%8A%E5%AF%BC%E4%BD%93",
  );
});

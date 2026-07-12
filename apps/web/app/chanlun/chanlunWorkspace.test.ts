import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const {
  CHANLUN_PERIODS,
  describeChanlunAvailability,
  isChanlunAnalysisCurrent,
  isChanlunSymbolCurrent,
  isChanlunWorkspaceCurrent,
  toChartPeriod,
  resolveChanlunPeriod,
} = (await import(
  new URL("./chanlunWorkspaceHelpers.ts", import.meta.url).href,
)) as typeof import("./chanlunWorkspaceHelpers");

test("workbench status marks insufficient history non-actionable", () => {
  assert.deepEqual(describeChanlunAvailability("insufficient_bars"), {
    tone: "neutral",
    text: "结构样本不足",
    actionable: false,
  });
});

test("workbench defaults to daily and exposes all four periods", () => {
  assert.equal(resolveChanlunPeriod(undefined), "1d");
  assert.deepEqual(CHANLUN_PERIODS, ["1d", "60m", "30m", "5m"]);
});

test("workbench maps every Chanlun period to its K-line chart period", () => {
  assert.equal(toChartPeriod("1d"), "daily");
  assert.equal(toChartPeriod("60m"), "60");
  assert.equal(toChartPeriod("30m"), "30");
  assert.equal(toChartPeriod("5m"), "5");
});

test("workbench hides analysis from a different selected period", () => {
  assert.equal(isChanlunAnalysisCurrent({ symbol: "600000.SH", period: "1d" }, "600000.SH", "5m"), false);
  assert.equal(isChanlunAnalysisCurrent({ symbol: "600000.SH", period: "5m" }, "600000.SH", "5m"), true);
});

test("workbench rejects a completed request for a previously selected symbol", () => {
  assert.equal(isChanlunSymbolCurrent("600000.SH", "000001.SZ"), false);
  assert.equal(isChanlunSymbolCurrent("600000.SH", "600000.SH"), true);
});

test("workbench hides a prior stock workspace while the new symbol loads", () => {
  assert.equal(isChanlunWorkspaceCurrent({ symbol: "600000.SH" }, "000001.SZ"), false);
  assert.equal(isChanlunWorkspaceCurrent({ symbol: "600000.SH" }, "600000.SH"), true);
});

test("Chanlun page loads the K-line chart stylesheet", () => {
  const pageSource = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

  assert.match(pageSource, /import "kline-charts-react\/style\.css"/);
});

test("K-line chart applies overlays after the base K-line data has loaded", () => {
  const chartSource = readFileSync(new URL("../../components/TickFlowKlineChart.tsx", import.meta.url), "utf8");

  assert.match(chartSource, /onDataLoad=\{handleDataLoad\}/);
  assert.match(chartSource, /setTimeout\(applyOverlay, 1000\)/);
  assert.match(chartSource, /buildChanlunClearSeries\(activeLayerIds\)/);
  assert.match(chartSource, /getEchartsInstance/);
  assert.match(chartSource, /\}, \[applyOverlay, echartsOption, indicatorLayout\]\);/);
  assert.doesNotMatch(chartSource, /echartsOption=\{echartsOption\}/);
});

test("Chanlun mobile chart toolbar preserves horizontal control labels", () => {
  const stylesheet = readFileSync(new URL("../globals.css", import.meta.url), "utf8");

  assert.match(stylesheet, /\.tickflow-kline-chart \[role="toolbar"\]/);
  assert.match(stylesheet, /white-space: nowrap/);
});

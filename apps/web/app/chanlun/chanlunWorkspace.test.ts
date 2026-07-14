import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const {
  CHANLUN_PERIODS,
  DEFAULT_CHANLUN_LAYERS,
  describeChanlunAvailability,
  groupCzscResearchEvidence,
  isChanlunAnalysisCurrent,
  isChanlunSymbolCurrent,
  isChanlunWorkspaceCurrent,
  toChartPeriod,
  resolveChanlunPeriod,
} = (await import(
  new URL("./chanlunWorkspaceHelpers.ts", import.meta.url).href,
)) as typeof import("./chanlunWorkspaceHelpers");

test("research evidence grouping keeps operational roles separate", () => {
  const groups = groupCzscResearchEvidence({ status: "ready", events: [
    { role: "primary" }, { role: "risk" }, { role: "primary" }, { role: "observation" },
  ] } as never);
  assert.deepEqual(Object.fromEntries(Object.entries(groups).map(([key, items]) => [key, items.length])), {
    primary: 2, confirmation: 0, risk: 1, observation: 1,
  });
});

test("workbench enables research signals and keeps moving averages disabled", () => {
  const source = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");
  assert.match(source, /\[showResearch, setShowResearch\] = useState\(true\)/);
  assert.match(source, /\[showMovingAverages, setShowMovingAverages\] = useState\(false\)/);
  assert.match(source, /上游研究信号/);
});

test("workbench separates analysis replay and simulation tasks", () => {
  const source = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");
  assert.match(source, /分析证据/);
  assert.match(source, /回放验证/);
  assert.match(source, /预警模拟/);
});

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

test("workbench opens with each available Chanlun structure layer visible", () => {
  assert.deepEqual(DEFAULT_CHANLUN_LAYERS, {
    divergences: true,
    fractals: true,
    segments: true,
    signals: true,
    strokes: true,
    zones: true,
  });
});

test("Chanlun workbench keeps moving averages hidden until enabled", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /\[showMovingAverages, setShowMovingAverages\] = useState\(false\)/);
  assert.match(workspaceSource, />\s*均线\s*</);
  assert.match(workspaceSource, /movingAverages=\{showMovingAverages \? \["ma5", "ma10", "ma20", "ma60"\] : \[\]\}/);
});

test("Chanlun workbench gives every period an expanded reading height", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");
  const stylesheet = readFileSync(new URL("../globals.css", import.meta.url), "utf8");

  assert.match(workspaceSource, /className="chanlun-status-rail__chart"/);
  assert.match(workspaceSource, /height=\{720\}/);
  assert.match(stylesheet, /\.chanlun-status-rail__chart\s*\{\s*height: 720px;/);
  assert.doesNotMatch(stylesheet, /\.chanlun-status-rail__chart\.is-daily/);
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

test("K-line chart waits for the matching native series before applying Chanlun overlays", () => {
  const chartSource = readFileSync(new URL("../../components/TickFlowKlineChart.tsx", import.meta.url), "utf8");

  assert.match(chartSource, /onDataLoad=\{handleDataLoad\}/);
  assert.match(chartSource, /useRef<KLineChartRef>/);
  assert.match(chartSource, /ref=\{chartRef\}/);
  assert.match(chartSource, /resolveKlineOverlaySeries/);
  assert.match(chartSource, /echartsOption=\{echartsOption\}/);
});

test("Chanlun overlays use the K-line library component directly", () => {
  const chartSource = readFileSync(new URL("../../components/TickFlowKlineChart.tsx", import.meta.url), "utf8");

  assert.match(chartSource, /KLineChart,[\s\S]*from "kline-charts-react"/);
  assert.match(chartSource, /<KLineChart/);
  assert.doesNotMatch(chartSource, /from "next\/dynamic"/);
});

test("K-line chart registers the ECharts component required by central-zone overlays", () => {
  const chartSource = readFileSync(new URL("../../components/TickFlowKlineChart.tsx", import.meta.url), "utf8");

  assert.match(chartSource, /MarkAreaComponent/);
  assert.match(chartSource, /useEcharts\(\[MarkAreaComponent\]\)/);
});

test("Chanlun mobile chart toolbar preserves horizontal control labels", () => {
  const stylesheet = readFileSync(new URL("../globals.css", import.meta.url), "utf8");

  assert.match(stylesheet, /\.tickflow-kline-chart \[role="toolbar"\]/);
  assert.match(stylesheet, /white-space: nowrap/);
});

test("Chanlun workbench presents confirmed server-side signals with their divergence coefficient", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /确认信号/);
  assert.match(workspaceSource, /activeAnalysis\?\.signals/);
  assert.match(workspaceSource, /formatDivergenceType/);
  assert.match(workspaceSource, /背驰系数/);
});

test("Chanlun workbench distinguishes five-stroke signals from divergence signals and shows period summaries", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /summary\?\.latest_signal/);
  assert.match(workspaceSource, /formatSignalBasis/);
  assert.match(workspaceSource, /五笔均线回抽/);
  assert.match(workspaceSource, /中枢离开未回抽/);
});

test("Chanlun workbench presents confirmed multi-period confluence separately from single-period signals", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /多周期共振/);
  assert.match(workspaceSource, /activeWorkspace\?\.confluence_signals/);
  assert.match(workspaceSource, /formatConfluenceType/);
  assert.match(workspaceSource, /higher_period/);
  assert.match(workspaceSource, /lower_period/);
});

test("Chanlun workbench runs historical replay on demand and renders its confirmed event timeline", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /getChanlunReplay/);
  assert.match(workspaceSource, /历史回放/);
  assert.match(workspaceSource, /replay\.frames/);
  assert.match(workspaceSource, /回放/);
});

test("Chanlun workbench runs a long-only performance backtest from confirmed replay events", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /getChanlunBacktest/);
  assert.match(workspaceSource, /绩效回测/);
  assert.match(workspaceSource, /backtest\.buckets/);
  assert.match(workspaceSource, /下一根 K 线开盘/);
});

test("Chanlun workbench makes alert baselining and newly confirmed signals explicit", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /refreshChanlunAlerts/);
  assert.match(workspaceSource, /预警记录/);
  assert.match(workspaceSource, /首次只建立基线/);
  assert.match(workspaceSource, /alerts\.items/);
});

test("Chanlun workbench creates local paper-order drafts and requires manual approval", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /createChanlunPaperOrderDraft/);
  assert.match(workspaceSource, /approveChanlunPaperOrder/);
  assert.match(workspaceSource, /模拟订单/);
  assert.match(workspaceSource, /人工确认/);
});

test("Chanlun workbench completes the local paper-order lifecycle", () => {
  const workspaceSource = readFileSync(new URL("./ChanlunWorkspace.tsx", import.meta.url), "utf8");

  assert.match(workspaceSource, /fillChanlunPaperOrder/);
  assert.match(workspaceSource, /cancelChanlunPaperOrder/);
  assert.match(workspaceSource, /更新成交/);
  assert.match(workspaceSource, /撤单/);
  assert.match(workspaceSource, /paperAccount\.positions/);
  assert.match(workspaceSource, /paperAccount\.total_equity/);
  assert.match(workspaceSource, /paperAccount\.unrealized_pnl/);
  assert.match(workspaceSource, /paperAccount\.valuation_complete/);
  assert.match(workspaceSource, /权益按成本暂估/);
  assert.match(workspaceSource, /行情暂不可用/);
  assert.match(workspaceSource, /仅本地模拟，不连接券商/);
});

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import type { AuctionModelPredictionItem, SectorRadarItem, StrongStockScreeningResponse } from "./types";
const {
  buildSectorFlowRows,
  executeLatestOnly,
  getAuctionCacheTradeDate,
  getMarketSession,
  getShanghaiTradeDate,
  isLatestRequestGeneration,
  marketBreadthPercent,
  nextRequestGeneration,
  selectScreenCandidates,
  selectTop3,
  selectWatchlistRisks,
  toPanelState,
} = (await import(new URL("./marketOverview.ts", import.meta.url).href)) as typeof import("./marketOverview");

test("decision queue avoids deprecated Ant Design Tag props", () => {
  const source = readFileSync(new URL("../components/overview/DecisionQueue.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(source, /bordered=\{false\}/);
});

test("decision queue keeps a missing Top3 cache recoverable", () => {
  const source = readFileSync(new URL("../components/overview/DecisionQueue.tsx", import.meta.url), "utf8");

  assert.match(source, /state\?\.kind === "missing"/);
  assert.match(source, /href="\/auction"/);
});

test("sector flow preview uses normalized rows and a mobile direction switch", () => {
  const source = readFileSync(new URL("../components/overview/SectorHeatmapPreview.tsx", import.meta.url), "utf8");

  assert.match(source, /buildSectorFlowRows/);
  assert.match(source, /aria-pressed/);
  assert.match(source, /sector-flow-chart/);
  assert.match(source, /sector-flow-heading/);
  assert.match(source, /sector-flow-track/);
});

test("market pulse exposes prominent breadth and compact index strip", () => {
  const source = readFileSync(new URL("../components/overview/MarketPulse.tsx", import.meta.url), "utf8");

  assert.match(source, /marketBreadthPercent/);
  assert.match(source, /market-state__value/);
  assert.match(source, /export function MarketIndexStrip/);
  assert.match(source, /market-index-strip/);
});

test("market pulse distinguishes pending panel data from failed data", () => {
  const source = readFileSync(new URL("../components/overview/MarketPulse.tsx", import.meta.url), "utf8");

  assert.match(source, /marketUnavailableLabel/);
  assert.match(source, /sentimentUnavailableLabel/);
  assert.match(source, /kind === "error" \? "读取失败" : "加载中"/);
});

test("homepage trend panels expose sector rotation and intraday emotion views", () => {
  const panelsUrl = new URL("../components/overview/MarketTrendPanels.tsx", import.meta.url);
  const chartUrl = new URL("../components/overview/OverviewTrendChart.tsx", import.meta.url);
  const panels = existsSync(panelsUrl) ? readFileSync(panelsUrl, "utf8") : "";
  const chart = existsSync(chartUrl) ? readFileSync(chartUrl, "utf8") : "";
  const styles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(panels, /板块轮动/);
  assert.match(panels, /盘中情绪走势/);
  assert.match(panels, /盘中样本不足/);
  assert.match(panels, /累计 2 个点后绘制/);
  assert.match(panels, /href="\/market\?view=sectors"/);
  assert.match(panels, /href="\/sentiment"/);
  assert.match(chart, /import\("echarts"\)/);
  assert.match(styles, /\.market-trend-grid/);
  assert.match(styles, /\.market-trend-chart/);
  assert.match(styles, /\.market-trend-summary/);
});

test("homepage only loads market direction data", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(source, /DecisionQueue/);
  assert.doesNotMatch(source, /getLatestScreenRun/);
  assert.doesNotMatch(source, /getAuctionModelTop3/);
  assert.match(source, /getMarketOverview/);
  assert.match(source, /getSectorRadar\(12\)/);
  assert.match(source, /getSentimentSummary\(tradeDate, 80, false\)/);
  assert.match(source, /getSectorReplicaRadar/);
  assert.match(source, /getMarketEmotionSnapshot/);
  assert.match(source, /MarketTrendPanels/);
  assert.match(source, /IntersectionObserver/);
  assert.match(source, /rootMargin: "240px"/);
  assert.doesNotMatch(source, /disabled=\{refreshing \|\| trendsRefreshing\}/);
  assert.doesNotMatch(source, /setTrendsRefreshing/);
  assert.doesNotMatch(source, /<MarketFeed/);
});

test("homepage applies core panels as each request settles", () => {
  const source = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.match(source, /runCorePanelRequest/);
  assert.match(source, /runCorePanelRequest\(getMarketOverview/);
  assert.match(source, /runCorePanelRequest\(\(\) => getSectorRadar\(12\)/);
  assert.match(source, /runCorePanelRequest\(\(\) => getSentimentSummary/);
  assert.doesNotMatch(source, /Promise\.allSettled\(\[[\s\S]*?getMarketOverview\(\)/);
});

test("homepage loading placeholder matches the focused composition", () => {
  const source = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

  assert.ok(source.indexOf("板块资金流") < source.indexOf("市场状态"));
  assert.ok(source.indexOf("市场状态") < source.indexOf("指数快照"));
  assert.ok(source.indexOf("指数快照") < source.indexOf("板块轮动"));
  assert.ok(source.indexOf("板块轮动") < source.indexOf("盘中情绪走势"));
  assert.doesNotMatch(source, /决策队列/);
  assert.doesNotMatch(source, /市场动态/);
});

test("decision queue uses content-height blocks and compact empty states", () => {
  const source = readFileSync(new URL("../components/overview/DecisionQueue.tsx", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(source, /decision-queue__grid/);
  assert.match(styles, /\.decision-queue__grid\s*\{[\s\S]*?align-items:\s*start/);
  assert.match(styles, /\.decision-queue \.ant-empty\s*\{[\s\S]*?margin-block:\s*0/);
  assert.match(styles, /\.decision-queue \.data-state--empty \.ant-empty-image\s*\{[\s\S]*?display:\s*none/);
  assert.match(styles, /\.market-index-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4/);
  assert.match(styles, /\.sector-flow-segment button\s*\{[\s\S]*?min-height:\s*44px/);
  assert.doesNotMatch(styles, /\.sector-flow-bar\s*\{[\s\S]*?min-width:\s*3px/);
});

test("desktop sector flow keeps labels and bars in normal flow", () => {
  const source = readFileSync(new URL("../components/overview/SectorHeatmapPreview.tsx", import.meta.url), "utf8");
  const styles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(source, /sector-flow-heading/);
  assert.match(source, /sector-flow-track/);
  assert.doesNotMatch(source, /sector-flow-bar__label/);
  assert.doesNotMatch(styles, /\.sector-flow-heading\s*\{[\s\S]*?position:\s*absolute/);
  assert.match(styles, /\.sector-flow-track\s*\{[\s\S]*?display:\s*flex/);
});

test("sector flow accessible labels state the direction explicitly", () => {
  const source = readFileSync(new URL("../components/overview/SectorHeatmapPreview.tsx", import.meta.url), "utf8");

  assert.match(source, /flowAriaLabel\(direction, row\)/);
  assert.match(source, /direction === "inflow" \? "净流入" : "净流出"/);
});

test("selectTop3 keeps only selected items in ascending rank order", () => {
  const items = [
    auctionItem("B", "selected", 2),
    auctionItem("A", "selected", 1),
    auctionItem("W", "watch", 0),
  ];

  assert.deepEqual(
    selectTop3(items).map((item) => item.symbol),
    ["A", "B"],
  );
});

test("selectTop3 places null ranks last", () => {
  const items = [
    auctionItem("N", "selected", null),
    auctionItem("B", "selected", 2),
    auctionItem("A", "selected", 1),
  ];

  assert.deepEqual(
    selectTop3(items).map((item) => item.symbol),
    ["A", "B", "N"],
  );
});

test("selectTop3 caps the queue at three selected items", () => {
  const items = [
    auctionItem("N", "selected", null),
    auctionItem("D", "selected", 4),
    auctionItem("C", "selected", 3),
    auctionItem("B", "selected", 2),
    auctionItem("A", "selected", 1),
  ];

  assert.deepEqual(
    selectTop3(items).map((item) => item.symbol),
    ["A", "B", "C"],
  );
});

test("selectScreenCandidates removes incomplete rows and caps the decision queue", () => {
  const response = screeningResponse([
    screeningItem("603001.SH", "focus"),
    screeningItem("300001.SZ", "wait_pullback"),
    screeningItem("600001.SH", "data_incomplete"),
    screeningItem("000002.SZ", "reduce_risk"),
    screeningItem("000003.SZ", "focus"),
    screeningItem("000004.SZ", "focus"),
    screeningItem("000005.SZ", "wait_pullback"),
    screeningItem("000006.SZ", "focus"),
  ]);

  const candidates = selectScreenCandidates(response);

  assert.deepEqual(
    candidates.map((item) => item.symbol),
    ["603001.SH", "300001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"],
  );
  assert.ok(candidates.every((item) => item.status !== "data_incomplete"));
  assert.ok(candidates.every((item) => item.status === "focus" || item.status === "wait_pullback" || item.status === "reduce_risk"));
});

test("selectWatchlistRisks returns at most three response risk rows", () => {
  const response = screeningResponse([]);
  response.watchlist_risk_items = [
    watchlistRiskItem("600001.SH", "hold_watch"),
    watchlistRiskItem("600002.SH", "reduce"),
    watchlistRiskItem("600003.SH", "empty"),
    watchlistRiskItem("600004.SH", "hold_watch"),
  ];

  assert.deepEqual(
    selectWatchlistRisks(response).map((item) => item.symbol),
    ["600001.SH", "600002.SH", "600003.SH"],
  );
});

test("sector flow rows ignore null values, keep four items, and normalize each direction", () => {
  const rows = buildSectorFlowRows([
    sectorItem("A", 20),
    sectorItem("B", 10),
    sectorItem("C", null),
    sectorItem("D", 5),
    sectorItem("E", 2),
    sectorItem("F", 1),
  ]);

  assert.deepEqual(
    rows.map((row) => [row.item.name, row.widthPercent]),
    [
      ["A", 100],
      ["B", 50],
      ["D", 25],
      ["E", 10],
    ],
  );
});

test("sector flow rows remain finite when the largest absolute flow is zero", () => {
  assert.deepEqual(buildSectorFlowRows([sectorItem("A", 0)]), [{ item: sectorItem("A", 0), widthPercent: 0 }]);
});

test("market breadth percentage excludes unchanged stocks and handles an empty denominator", () => {
  assert.equal(marketBreadthPercent(3772, 1678), 69.21);
  assert.equal(marketBreadthPercent(null, 10), 0);
  assert.equal(marketBreadthPercent(0, 0), 0);
});

test("toPanelState reports an initial rejected panel as an error", () => {
  assert.deepEqual(toPanelState({ status: "rejected", reason: new Error("timeout") }), {
    kind: "error",
    value: null,
  });
});

test("toPanelState retains a prior value as stale after a rejected refresh", () => {
  assert.deepEqual(toPanelState({ status: "rejected", reason: new Error("timeout") }, { value: 42 }), {
    kind: "stale",
    value: { value: 42 },
  });
});

test("toPanelState marks fulfilled results ready", () => {
  assert.deepEqual(toPanelState({ status: "fulfilled", value: { value: 42 } }), {
    kind: "ready",
    value: { value: 42 },
  });
});

test("a newer refresh generation supersedes the previous request", () => {
  const firstRequest = nextRequestGeneration(0);
  const secondRequest = nextRequestGeneration(firstRequest);

  assert.equal(isLatestRequestGeneration(firstRequest, secondRequest), false);
  assert.equal(isLatestRequestGeneration(secondRequest, secondRequest), true);
});

test("only the latest refresh generation can apply results or clear refreshing", () => {
  const activeRequest = nextRequestGeneration(4);

  assert.equal(isLatestRequestGeneration(4, activeRequest), false);
  assert.equal(isLatestRequestGeneration(activeRequest, activeRequest), true);
});

test("latest-only execution applies and finishes only the newest settled batch", async () => {
  const firstBatch = Array.from({ length: 5 }, () => deferred<string>());
  const secondBatch = Array.from({ length: 5 }, () => deferred<string>());
  const firstGeneration = nextRequestGeneration(0);
  const secondGeneration = nextRequestGeneration(firstGeneration);
  let currentGeneration = firstGeneration;
  const applied: string[][] = [];
  const finished: number[] = [];

  const firstExecution = executeLatestOnly({
    generation: firstGeneration,
    currentGeneration: () => currentGeneration,
    execute: () => Promise.allSettled(firstBatch.map((item) => item.promise)),
    apply: (results) => applied.push(settledValues(results)),
    finishLoading: () => finished.push(firstGeneration),
  });

  currentGeneration = secondGeneration;
  const secondExecution = executeLatestOnly({
    generation: secondGeneration,
    currentGeneration: () => currentGeneration,
    execute: () => Promise.allSettled(secondBatch.map((item) => item.promise)),
    apply: (results) => applied.push(settledValues(results)),
    finishLoading: () => finished.push(secondGeneration),
  });

  secondBatch.forEach((item, index) => item.resolve(`second-${index + 1}`));
  assert.equal(await secondExecution, true);
  assert.deepEqual(applied, [["second-1", "second-2", "second-3", "second-4", "second-5"]]);
  assert.deepEqual(finished, [secondGeneration]);

  firstBatch.forEach((item, index) => item.resolve(`first-${index + 1}`));
  assert.equal(await firstExecution, false);
  assert.deepEqual(applied, [["second-1", "second-2", "second-3", "second-4", "second-5"]]);
  assert.deepEqual(finished, [secondGeneration]);
});

test("getShanghaiTradeDate uses the Shanghai calendar date", () => {
  assert.equal(getShanghaiTradeDate(new Date("2026-07-09T16:30:00.000Z")), "2026-07-10");
  assert.equal(getShanghaiTradeDate(new Date("2026-07-10T16:30:00.000Z")), "2026-07-11");
});

test("getAuctionCacheTradeDate uses Friday during the weekend", () => {
  assert.equal(getAuctionCacheTradeDate(new Date("2026-07-10T16:30:00.000Z")), "2026-07-10");
  assert.equal(getAuctionCacheTradeDate(new Date("2026-07-11T16:30:00.000Z")), "2026-07-10");
  assert.equal(getAuctionCacheTradeDate(new Date("2026-07-12T16:30:00.000Z")), "2026-07-13");
});

test("getMarketSession labels Shanghai auction, trading, lunch, and close", () => {
  assert.equal(getMarketSession(new Date("2026-07-10T01:29:00.000Z")), "盘前竞价");
  assert.equal(getMarketSession(new Date("2026-07-10T01:30:00.000Z")), "盘中");
  assert.equal(getMarketSession(new Date("2026-07-10T03:29:00.000Z")), "盘中");
  assert.equal(getMarketSession(new Date("2026-07-10T03:30:00.000Z")), "收盘复盘");
  assert.equal(getMarketSession(new Date("2026-07-10T04:00:00.000Z")), "收盘复盘");
  assert.equal(getMarketSession(new Date("2026-07-10T05:00:00.000Z")), "盘中");
  assert.equal(getMarketSession(new Date("2026-07-10T06:59:00.000Z")), "盘中");
  assert.equal(getMarketSession(new Date("2026-07-10T07:00:00.000Z")), "收盘复盘");
});

test("getMarketSession labels Shanghai weekends as closed", () => {
  assert.equal(getMarketSession(new Date("2026-07-11T02:00:00.000Z")), "休市");
  assert.equal(getMarketSession(new Date("2026-07-12T05:00:00.000Z")), "休市");
});

function auctionItem(
  symbol: string,
  bucket: AuctionModelPredictionItem["bucket"],
  rank: number | null,
): AuctionModelPredictionItem {
  return {
    symbol,
    name: symbol,
    prob_3pct: 0.5,
    bucket,
    rank,
    prev_close_price: null,
    market_cap_float: null,
    avg_amount_3d: null,
    feature_end_date: null,
    guard_rule: null,
    strategy_note: null,
    trend_reasons: [],
    risk_flags: [],
    data_quality: [],
  };
}

function screeningItem(
  symbol: string,
  status: StrongStockScreeningResponse["items"][number]["status"],
): StrongStockScreeningResponse["items"][number] {
  return {
    symbol,
    name: symbol,
    industry: null,
    industry_strength: null,
    industry_score: 0,
    industry_rank: null,
    industry_notes: [],
    status,
    score: 0,
    rule_hits: [],
    risk_flags: [],
    severe_abnormal_warning: "clear",
    negative_news_status: "clear",
    negative_news_flags: [],
    intraday_notes: [],
    metrics: {},
    data_status: "complete",
    source_trace: [],
    gsgf: null,
  };
}

function sectorItem(name: string, netFlowCny: number | null): SectorRadarItem {
  return {
    name,
    source: "test",
    change_pct: 1,
    turnover_cny: 100,
    advance_count: 1,
    decline_count: 0,
    leader: `${name} leader`,
    net_flow_cny: netFlowCny,
    strength_score: 10,
  };
}

function screeningResponse(items: StrongStockScreeningResponse["items"]): StrongStockScreeningResponse {
  return {
    strategy: "combined",
    strong_model_version: "test",
    gsgf_model_version: null,
    sort_version: "test",
    trade_date: "2026-07-10",
    source_status: [],
    items,
    gsgf_funnel: {
      candidate_pool_count: 0,
      after_static_filters_count: 0,
      scan_limit_count: 0,
      kline_success_count: 0,
      kline_failure_count: 0,
      data_incomplete_count: 0,
      kdj_filtered_count: 0,
      gsgf_structure_hit_count: 0,
      confirmed_buy_count: 0,
      low_buy_count: 0,
      b_zone_a_point_count: 0,
      volume_breakout_count: 0,
      hard_risk_filtered_count: 0,
      final_displayed_count: 0,
    },
    gsgf_observation_items: [],
    watchlist_risk_items: [],
    generated_at: "2026-07-10T00:00:00+08:00",
  };
}

function watchlistRiskItem(
  symbol: string,
  riskAction: StrongStockScreeningResponse["watchlist_risk_items"][number]["risk_action"],
): StrongStockScreeningResponse["watchlist_risk_items"][number] {
  return {
    symbol,
    name: symbol,
    industry: null,
    risk_action: riskAction,
    risk_flags: [],
    severe_abnormal_warning: "clear",
    negative_news_status: "clear",
    negative_news_flags: [],
    intraday_notes: [],
    metrics: {},
    source_trace: [],
    gsgf: null,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function settledValues(results: PromiseSettledResult<string>[]) {
  return results.map((result) => (result.status === "fulfilled" ? result.value : "rejected"));
}

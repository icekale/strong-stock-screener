import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { AuctionModelPredictionItem, StrongStockScreeningResponse } from "./types";
const {
  executeLatestOnly,
  getAuctionCacheTradeDate,
  getMarketSession,
  getShanghaiTradeDate,
  isLatestRequestGeneration,
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
  const workbenchSource = readFileSync(new URL("../app/MarketOverviewWorkbench.tsx", import.meta.url), "utf8");

  assert.match(source, /state\?\.kind === "missing"/);
  assert.match(source, /href="\/auction"/);
  assert.match(workbenchSource, /getAuctionCacheTradeDate\(\)/);
  assert.match(workbenchSource, /isAuctionModelTop3CacheMiss/);
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

import assert from "node:assert/strict";
import test from "node:test";
const {
  createChanlunBackfillJob,
  getCzscResearchSignals,
  getAuctionModelTop3,
  getChanlunAnalysis,
  getChanlunAlerts,
  getChanlunBackfillJob,
  getChanlunBacktest,
  getChanlunPaperAccount,
  getChanlunReplay,
  getChanlunWorkspace,
  isAuctionModelTop3CacheMiss,
  approveChanlunPaperOrder,
  cancelChanlunPaperOrder,
  createChanlunPaperOrderDraft,
  fillChanlunPaperOrder,
  refreshChanlunAlerts,
  searchChanlunSymbols,
} =
  (await import(new URL("./api.ts", import.meta.url).href)) as typeof import("./api");

test("cache-only Top3 marks a missing cache separately from an API failure", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "暂无缓存的竞价模型Top3结果" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });

  try {
    await assert.rejects(
      () => getAuctionModelTop3("2026-07-11", { cacheOnly: true }),
      (error: unknown) => isAuctionModelTop3CacheMiss(error),
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Chanlun client encodes symbols and analysis query parameters", async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ url: URL; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: new URL(String(input)), init });
    return new Response(JSON.stringify({}), { headers: { "Content-Type": "application/json" } });
  };

  try {
    await getChanlunAnalysis("600000.SH/test", {
      period: "5m",
      lookback: 120,
      includeObserving: true,
    });
    await getCzscResearchSignals("600000.SH/test", { lookback: 220 });
    await getChanlunWorkspace("600000.SH/test", { lookback: 180 });
    await getChanlunReplay("600000.SH/test", { period: "30m", lookback: 180 });
    await getChanlunBacktest("600000.SH/test", { period: "30m", lookback: 180 });
    await getChanlunAlerts({ symbol: "600000.SH/test", limit: 5 });
    await refreshChanlunAlerts("600000.SH/test", { period: "30m", lookback: 180 });
    await createChanlunPaperOrderDraft("600000.SH/test", { quantity: 100, lookback: 180 });
    await approveChanlunPaperOrder("paper/test");
    await cancelChanlunPaperOrder("paper/test");
    await fillChanlunPaperOrder("paper/test");
    await getChanlunPaperAccount();
    await searchChanlunSymbols("浦发 银行", { limit: 5 });
    await createChanlunBackfillJob("600000.SH/test", { history_days: 60 });
    await getChanlunBackfillJob("600000.SH/test", "job/1");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(requests[0].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/analysis");
  assert.equal(requests[0].url.searchParams.get("period"), "5m");
  assert.equal(requests[0].url.searchParams.get("lookback"), "120");
  assert.equal(requests[0].url.searchParams.get("include_observing"), "true");
  assert.equal(requests[1].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/research-signals");
  assert.equal(requests[1].url.searchParams.get("lookback"), "220");
  assert.equal(requests[2].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/workspace");
  assert.equal(requests[2].url.searchParams.get("lookback"), "180");
  assert.equal(requests[3].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/replays");
  assert.equal(requests[3].url.searchParams.get("period"), "30m");
  assert.equal(requests[3].url.searchParams.get("lookback"), "180");
  assert.equal(requests[4].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/backtests");
  assert.equal(requests[4].url.searchParams.get("period"), "30m");
  assert.equal(requests[4].url.searchParams.get("lookback"), "180");
  assert.equal(requests[5].url.pathname, "/api/chanlun/alerts");
  assert.equal(requests[5].url.searchParams.get("symbol"), "600000.SH/test");
  assert.equal(requests[5].url.searchParams.get("limit"), "5");
  assert.equal(requests[6].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/alerts/refresh");
  assert.equal(requests[6].url.searchParams.get("period"), "30m");
  assert.equal(requests[6].url.searchParams.get("lookback"), "180");
  assert.equal(requests[6].init?.method, "POST");
  assert.equal(requests[7].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/paper-orders/drafts");
  assert.equal(requests[7].url.searchParams.get("lookback"), "180");
  assert.equal(requests[7].init?.method, "POST");
  assert.equal(requests[7].init?.body, JSON.stringify({ quantity: 100 }));
  assert.equal(requests[8].url.pathname, "/api/chanlun/paper-orders/paper%2Ftest/approve");
  assert.equal(requests[8].init?.method, "POST");
  assert.equal(requests[9].url.pathname, "/api/chanlun/paper-orders/paper%2Ftest/cancel");
  assert.equal(requests[9].init?.method, "POST");
  assert.equal(requests[10].url.pathname, "/api/chanlun/paper-orders/paper%2Ftest/fill");
  assert.equal(requests[10].init?.method, "POST");
  assert.equal(requests[11].url.pathname, "/api/chanlun/paper-account");
  assert.equal(requests[12].url.searchParams.get("query"), "浦发 银行");
  assert.equal(requests[12].url.searchParams.get("limit"), "5");
  assert.equal(requests[13].init?.method, "POST");
  assert.equal(requests[13].init?.body, JSON.stringify({ history_days: 60 }));
  assert.equal(requests[14].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/backfill/job%2F1");
});

test("Chanlun client errors include response status and body", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("source unavailable", { status: 503 });

  try {
    await assert.rejects(
      () => getChanlunAnalysis("600000.SH"),
      (error: unknown) => {
        assert.match(String(error), /503/);
        assert.match(String(error), /source unavailable/);
        return true;
      },
    );
    await assert.rejects(
      () => getCzscResearchSignals("600000.SH"),
      (error: unknown) => {
        assert.match(String(error), /503/);
        assert.match(String(error), /source unavailable/);
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

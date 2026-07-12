import assert from "node:assert/strict";
import test from "node:test";
const {
  createChanlunBackfillJob,
  getAuctionModelTop3,
  getChanlunAnalysis,
  getChanlunBackfillJob,
  getChanlunWorkspace,
  isAuctionModelTop3CacheMiss,
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
    await getChanlunWorkspace("600000.SH/test", { lookback: 180 });
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
  assert.equal(requests[1].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/workspace");
  assert.equal(requests[1].url.searchParams.get("lookback"), "180");
  assert.equal(requests[2].url.searchParams.get("query"), "浦发 银行");
  assert.equal(requests[2].url.searchParams.get("limit"), "5");
  assert.equal(requests[3].init?.method, "POST");
  assert.equal(requests[3].init?.body, JSON.stringify({ history_days: 60 }));
  assert.equal(requests[4].url.pathname, "/api/chanlun/stocks/600000.SH%2Ftest/backfill/job%2F1");
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
  } finally {
    globalThis.fetch = originalFetch;
  }
});

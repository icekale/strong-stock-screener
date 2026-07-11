import assert from "node:assert/strict";
import test from "node:test";
const { getAuctionModelTop3, isAuctionModelTop3CacheMiss } =
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

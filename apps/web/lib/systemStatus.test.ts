import assert from "node:assert/strict";
import test from "node:test";

import type { SystemCacheItem, SystemStatusResponse } from "./types";

const { cacheFreshnessLabel, cacheStatusTone, systemStatusTone } = (await import(
  new URL("./systemStatus.ts", import.meta.url).href
)) as typeof import("./systemStatus");
const { clearSystemCache } = (await import(new URL("./api.ts", import.meta.url).href)) as typeof import("./api");

function cache(overrides: Partial<SystemCacheItem> = {}): SystemCacheItem {
  return {
    name: "market_overview",
    group: "home",
    ttl_seconds: 45,
    size: 1,
    fresh_count: 1,
    refreshing_count: 0,
    hits: 3,
    misses: 1,
    stale_hits: 0,
    refresh_count: 1,
    refresh_error_count: 0,
    last_refresh_started_at: null,
    last_refresh_finished_at: null,
    last_error: null,
    oldest_expires_in_seconds: 12.3,
    ...overrides,
  };
}

test("cacheFreshnessLabel formats fresh cache", () => {
  assert.equal(cacheFreshnessLabel(cache()), "12秒后过期");
});

test("cacheFreshnessLabel formats stale cache", () => {
  assert.equal(cacheFreshnessLabel(cache({ fresh_count: 0, oldest_expires_in_seconds: -20 })), "已过期20秒");
});

test("cacheFreshnessLabel formats empty cache with unknown expiry", () => {
  assert.equal(cacheFreshnessLabel(cache({ size: 0, oldest_expires_in_seconds: null })), "暂无缓存");
});

test("cacheFreshnessLabel formats populated cache with unknown expiry", () => {
  assert.equal(cacheFreshnessLabel(cache({ size: 2, oldest_expires_in_seconds: null })), "缓存状态未知");
});

test("cacheStatusTone marks only current cache errors as error", () => {
  assert.equal(cacheStatusTone(cache({ refresh_error_count: 2, last_error: null })), "fresh");
  assert.equal(cacheStatusTone(cache({ refresh_error_count: 2, last_error: "timeout" })), "error");
  assert.equal(cacheStatusTone(cache({ refresh_error_count: 2, last_error: "" })), "error");
});

test("cacheStatusTone separates stale cache from recovered historical errors", () => {
  assert.equal(
    cacheStatusTone(cache({ fresh_count: 0, refresh_error_count: 2, last_error: null })),
    "stale",
  );
});

test("systemStatusTone maps degraded systems to warning", () => {
  const status: SystemStatusResponse = {
    status: "degraded",
    generated_at: "2026-07-05T10:00:00+08:00",
    confidence: "degraded",
    cache: { total: 1, items: [cache({ refresh_error_count: 1, last_error: "timeout" })] },
    jobs: [],
  };
  assert.equal(systemStatusTone(status), "warning");
});

test("systemStatusTone maps fresh ok systems to success", () => {
  const status: SystemStatusResponse = {
    status: "ok",
    generated_at: "2026-07-05T10:00:00+08:00",
    confidence: "fresh",
    cache: { total: 1, items: [cache()] },
    jobs: [],
  };
  assert.equal(systemStatusTone(status), "success");
});

test("systemStatusTone maps non-fresh ok systems to warning", () => {
  const status: SystemStatusResponse = {
    status: "ok",
    generated_at: "2026-07-05T10:00:00+08:00",
    confidence: "partial",
    cache: { total: 1, items: [cache()] },
    jobs: [],
  };
  assert.equal(systemStatusTone(status), "warning");
});

test("clearSystemCache rejects blank groups without calling fetch", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response(JSON.stringify({ cleared: [] }), { status: 200 });
  }) as typeof fetch;

  try {
    for (const group of ["", "   ", "\n\t"]) {
      await assert.rejects(() => clearSystemCache(group), /缓存分组不能为空/);
    }
    assert.equal(calls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("clearSystemCache trims valid group before calling backend", async () => {
  const originalFetch = globalThis.fetch;
  let requestUrl = "";
  let requestInit: RequestInit | undefined;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    requestUrl = String(input);
    requestInit = init;
    return new Response(JSON.stringify({ cleared: ["market_overview"] }), { status: 200 });
  }) as typeof fetch;

  try {
    const response = await clearSystemCache(" home ");

    assert.deepEqual(response, { cleared: ["market_overview"] });
    assert.match(requestUrl, /\/api\/system\/cache\/clear\?group=home$/);
    assert.equal(requestInit?.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

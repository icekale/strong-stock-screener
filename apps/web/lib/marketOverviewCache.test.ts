import assert from "node:assert/strict";
import test from "node:test";
const { createMemoryRequestCache } = (await import(
  new URL("./marketOverviewCache.ts", import.meta.url).href,
)) as typeof import("./marketOverviewCache");

test("cache returns a fresh value without repeating the request", async () => {
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = async () => {
    calls += 1;
    return "market";
  };

  assert.equal(await cache.get("market:2026-07-18", request), "market");
  assert.equal(await cache.get("market:2026-07-18", request), "market");
  assert.equal(calls, 1);
});

test("cache expires values after the configured TTL", async () => {
  let now = 1000;
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => now, ttlMs: 15_000 });
  const request = async () => ++calls;

  assert.equal(await cache.get("market", request), 1);
  now = 16_001;
  assert.equal(await cache.get("market", request), 2);
});

test("cache shares an in-flight request for the same key", async () => {
  let resolveRequest!: (value: string) => void;
  let calls = 0;
  const pending = new Promise<string>((resolve) => {
    resolveRequest = resolve;
  });
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = () => {
    calls += 1;
    return pending;
  };

  const first = cache.get("sector", request);
  const second = cache.get("sector", request);
  assert.equal(first, second);
  resolveRequest("sector");
  assert.equal(await first, "sector");
  assert.equal(calls, 1);
});

test("force refresh bypasses the cached value and failures do not poison it", async () => {
  let calls = 0;
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });
  const request = async () => {
    calls += 1;
    if (calls === 2) throw new Error("temporary failure");
    return calls;
  };

  assert.equal(await cache.get("emotion", request), 1);
  await assert.rejects(cache.get("emotion", request, { force: true }), /temporary failure/);
  assert.equal(await cache.get("emotion", request), 1);
  assert.equal(calls, 2);
});

test("an older forced request cannot overwrite a newer forced request", async () => {
  let resolveOld!: (value: string) => void;
  let resolveNew!: (value: string) => void;
  const oldRequest = new Promise<string>((resolve) => {
    resolveOld = resolve;
  });
  const newRequest = new Promise<string>((resolve) => {
    resolveNew = resolve;
  });
  const cache = createMemoryRequestCache({ now: () => 1000, ttlMs: 15_000 });

  const old = cache.get("market", () => oldRequest, { force: true });
  const fresh = cache.get("market", () => newRequest, { force: true });
  resolveNew("new");
  assert.equal(await fresh, "new");
  resolveOld("old");
  assert.equal(await old, "old");
  assert.equal(await cache.get("market", async () => "unexpected"), "new");
});

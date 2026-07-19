import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const { normalizeMarketView } = (await import(
  new URL("./marketWorkspace.ts", import.meta.url).href
)) as typeof import("./marketWorkspace");

test("market view normalization keeps heatmap and defaults invalid views to sectors", () => {
  assert.equal(normalizeMarketView("heatmap"), "heatmap");
  assert.equal(normalizeMarketView(null), "sectors");
  assert.equal(normalizeMarketView("unknown"), "sectors");
});

test("market workspace exposes a direct ETF funds entry", () => {
  const source = readFileSync(new URL("../app/market/MarketWorkspace.tsx", import.meta.url), "utf8");

  assert.match(source, /label: "ETF资金", value: "etf"/);
  assert.match(source, /value === "etf"/);
  assert.match(source, /router\.push\("\/etf-radar"\)/);
});

import assert from "node:assert/strict";
import test from "node:test";

const { normalizeMarketView } = (await import(
  new URL("./marketWorkspace.ts", import.meta.url).href
)) as typeof import("./marketWorkspace");

test("market view normalization keeps heatmap and defaults invalid views to sectors", () => {
  assert.equal(normalizeMarketView("heatmap"), "heatmap");
  assert.equal(normalizeMarketView(null), "sectors");
  assert.equal(normalizeMarketView("unknown"), "sectors");
});

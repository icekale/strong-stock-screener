import assert from "node:assert/strict";
import test from "node:test";

const { getLegacyDestination, getNavigationSelection, navigationGroups } = (await import(
  new URL("./appNavigation.ts", import.meta.url).href,
)) as typeof import("./appNavigation");

test("navigation groups preserve the market decision path", () => {
  assert.deepEqual(navigationGroups.map((group) => group.label), ["市场", "观察", "系统"]);
  assert.deepEqual(getNavigationSelection("/auction"), { groupKey: "market", itemKey: "auction" });
  assert.deepEqual(getNavigationSelection("/auction/history"), { groupKey: "market", itemKey: "auction" });
  assert.deepEqual(getNavigationSelection("/auctioneering"), { groupKey: "market", itemKey: "overview" });
  assert.deepEqual(getNavigationSelection("/stock/603823.SH"), { groupKey: "market", itemKey: null });
});

test("legacy routes resolve to unified workspaces", () => {
  assert.equal(getLegacyDestination("/sectors"), "/market?view=sectors");
  assert.equal(getLegacyDestination("/heatmap"), "/market?view=heatmap");
  assert.equal(getLegacyDestination("/model-maintenance"), "/system?tab=model");
  assert.equal(getLegacyDestination("/settings"), "/system?tab=data");
  assert.equal(getLegacyDestination("/unknown"), null);
});

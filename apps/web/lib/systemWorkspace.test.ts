import assert from "node:assert/strict";
import test from "node:test";

const { buildSystemTabHref, createVisitedSystemTabs, normalizeSystemTab, visitSystemTab } = (await import(
  new URL("./systemWorkspace.ts", import.meta.url).href
)) as typeof import("./systemWorkspace");

test("system tab normalization preserves model and data", () => {
  assert.equal(normalizeSystemTab("model"), "model");
  assert.equal(normalizeSystemTab("data"), "data");
});

test("system tab normalization defaults null and unknown values to model", () => {
  assert.equal(normalizeSystemTab(null), "model");
  assert.equal(normalizeSystemTab("unknown"), "model");
});

test("visited system tabs initially contain only the current tab", () => {
  assert.deepEqual(createVisitedSystemTabs("model"), ["model"]);
  assert.deepEqual(createVisitedSystemTabs("data"), ["data"]);
});

test("visiting data retains both model and data tabs", () => {
  assert.deepEqual(visitSystemTab(["model"], "data"), ["model", "data"]);
});

test("system tab URLs preserve model and data values", () => {
  assert.equal(buildSystemTabHref("model"), "/system?tab=model");
  assert.equal(buildSystemTabHref("data"), "/system?tab=data");
});

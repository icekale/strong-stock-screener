import assert from "node:assert/strict";
import test from "node:test";

const {
  CHANLUN_PERIODS,
  describeChanlunAvailability,
  isChanlunAnalysisCurrent,
  isChanlunSymbolCurrent,
  isChanlunWorkspaceCurrent,
  resolveChanlunPeriod,
} = (await import(
  new URL("./chanlunWorkspaceHelpers.ts", import.meta.url).href,
)) as typeof import("./chanlunWorkspaceHelpers");

test("workbench status marks insufficient history non-actionable", () => {
  assert.deepEqual(describeChanlunAvailability("insufficient_bars"), {
    tone: "neutral",
    text: "结构样本不足",
    actionable: false,
  });
});

test("workbench defaults to daily and exposes all four periods", () => {
  assert.equal(resolveChanlunPeriod(undefined), "1d");
  assert.deepEqual(CHANLUN_PERIODS, ["1d", "60m", "30m", "5m"]);
});

test("workbench hides analysis from a different selected period", () => {
  assert.equal(isChanlunAnalysisCurrent({ symbol: "600000.SH", period: "1d" }, "600000.SH", "5m"), false);
  assert.equal(isChanlunAnalysisCurrent({ symbol: "600000.SH", period: "5m" }, "600000.SH", "5m"), true);
});

test("workbench rejects a completed request for a previously selected symbol", () => {
  assert.equal(isChanlunSymbolCurrent("600000.SH", "000001.SZ"), false);
  assert.equal(isChanlunSymbolCurrent("600000.SH", "600000.SH"), true);
});

test("workbench hides a prior stock workspace while the new symbol loads", () => {
  assert.equal(isChanlunWorkspaceCurrent({ symbol: "600000.SH" }, "000001.SZ"), false);
  assert.equal(isChanlunWorkspaceCurrent({ symbol: "600000.SH" }, "600000.SH"), true);
});

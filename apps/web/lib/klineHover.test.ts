import assert from "node:assert/strict";
import test from "node:test";

const { formatKlineHoverDate, resolveCurrentPriceLabelX, resolveKlineHoverIndex } = (await import(
  new URL("./klineHover.ts", import.meta.url).href
)) as typeof import("./klineHover");

test("resolveKlineHoverIndex maps pointer positions to the nearest candle", () => {
  const chartWidth = 100;
  const plotLeft = 10;
  const plotRight = 90;
  const barCount = 8;

  assert.equal(resolveKlineHoverIndex(0, 200, chartWidth, plotLeft, plotRight, barCount), null);
  assert.equal(resolveKlineHoverIndex(30, 200, chartWidth, plotLeft, plotRight, barCount), 0);
  assert.equal(resolveKlineHoverIndex(100, 200, chartWidth, plotLeft, plotRight, barCount), 4);
  assert.equal(resolveKlineHoverIndex(180, 200, chartWidth, plotLeft, plotRight, barCount), 7);
});

test("formatKlineHoverDate renders yyyymmdd values with separators", () => {
  assert.equal(formatKlineHoverDate("20260615"), "2026-06-15");
  assert.equal(formatKlineHoverDate("2026-06-15"), "2026-06-15");
});

test("resolveCurrentPriceLabelX prefers the right axis gutter when available", () => {
  assert.equal(resolveCurrentPriceLabelX(1120, 1048, 56), 1056);
  assert.equal(resolveCurrentPriceLabelX(200, 180, 56), 116);
});

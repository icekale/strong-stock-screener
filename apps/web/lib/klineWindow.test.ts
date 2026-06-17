import assert from "node:assert/strict";
import test from "node:test";

const { nextKlineWindowSize, sliceKlineWindow } = (await import(
  new URL("./klineWindow.ts", import.meta.url).href
)) as typeof import("./klineWindow");

test("kline window zooms in and out within available bars", () => {
  assert.equal(nextKlineWindowSize(120, "in", 220), 90);
  assert.equal(nextKlineWindowSize(30, "in", 220), 30);
  assert.equal(nextKlineWindowSize(120, "out", 220), 160);
  assert.equal(nextKlineWindowSize(200, "out", 220), 220);
  assert.equal(nextKlineWindowSize(120, "all", 220), 220);
});

test("sliceKlineWindow returns the latest visible window", () => {
  const bars: Array<{ date: string }> = Array.from({ length: 8 }, (_, index) => ({ date: String(index) }));

  assert.deepEqual(
    sliceKlineWindow(bars, 3).map((bar) => bar.date),
    ["5", "6", "7"],
  );
  assert.deepEqual(
    sliceKlineWindow(bars, 20).map((bar) => bar.date),
    ["0", "1", "2", "3", "4", "5", "6", "7"],
  );
});

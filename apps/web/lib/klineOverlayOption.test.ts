import assert from "node:assert/strict";
import test from "node:test";

const {
  buildTickFlowOverlayOption,
} = (await import(new URL("./brickIndicator.ts", import.meta.url).href)) as typeof import("./brickIndicator");

test("tickflow overlay option omits the annotation series when no annotation is visible", () => {
  const option = buildTickFlowOverlayOption({
    annotations: [],
    chartData: [
      { amount: null, close: 10, date: "2026-01-01", high: 11, low: 9, open: 9.5, volume: 1000 },
    ],
    showGsgfAnnotations: false,
    subIndicators: ["volume"],
  });

  assert.equal(option.series, undefined);
});

test("tickflow overlay option never emits a series without an explicit type", () => {
  const option = buildTickFlowOverlayOption({
    annotations: [
      {
        date: "20260102",
        end_date: "20260103",
        label: "B区A点",
        description: "结构确认",
        price: 10.8,
        severity: "positive",
        start_date: "20260101",
        type: "trigger",
      },
    ],
    chartData: [
      { amount: null, close: 10, date: "2026-01-01", high: 11, low: 9, open: 9.5, volume: 1000 },
      { amount: null, close: 11, date: "2026-01-02", high: 11.5, low: 10, open: 10.2, volume: 1200 },
    ],
    showGsgfAnnotations: true,
    subIndicators: ["brick"],
  });

  const series = Array.isArray(option.series) ? option.series : [];
  assert.equal(series.length, 2);
  assert.deepEqual(series.map((item) => item.type), ["candlestick", "candlestick"]);
  assert.deepEqual(series.map((item) => item.name), ["GSGF标注", "砖形图"]);
});

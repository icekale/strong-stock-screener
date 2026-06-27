import assert from "node:assert/strict";
import test from "node:test";

const {
  buildBrickIndicatorSeries,
  calculateBrickIndicator,
} = (await import(new URL("./brickIndicator.ts", import.meta.url).href)) as typeof import("./brickIndicator");

test("calculateBrickIndicator follows the Tonghuashun brick formula", () => {
  const points = calculateBrickIndicator([
    { close: 7, date: "2026-01-01", high: 10, low: 5 },
    { close: 11, date: "2026-01-02", high: 12, low: 6 },
    { close: 5, date: "2026-01-03", high: 11, low: 4 },
  ]);

  assert.deepEqual(
    points.map((point) => ({
      date: point.date,
      rising: point.rising,
      value: Number(point.value.toFixed(2)),
    })),
    [
      { date: "2026-01-01", rising: true, value: 66 },
      { date: "2026-01-02", rising: true, value: 78.7 },
      { date: "2026-01-03", rising: false, value: 69.05 },
    ],
  );
});

test("buildBrickIndicatorSeries maps the custom indicator to the selected sub pane", () => {
  const series = calculateBrickIndicator([
    { close: 7, date: "2026-01-01", high: 10, low: 5 },
    { close: 11, date: "2026-01-02", high: 12, low: 6 },
    { close: 5, date: "2026-01-03", high: 11, low: 4 },
  ]);
  const chartSeries = buildBrickIndicatorSeries(series, ["macd", "brick"]);

  assert.equal(chartSeries.length, 1);
  assert.equal(chartSeries[0].id, "custom-brick-1");
  assert.equal(chartSeries[0].name, "砖形图");
  assert.equal(chartSeries[0].type, "candlestick");
  assert.equal(chartSeries[0].xAxisIndex, 2);
  assert.equal(chartSeries[0].yAxisIndex, 2);
  const brickCandles = chartSeries[0].data as Array<{ value: number[] }>;
  assert.deepEqual(
    brickCandles.map((item) => item.value.map((value) => Number(value.toFixed(2)))),
    [
      [66, 66, 66, 66],
      [66, 78.7, 66, 78.7],
      [78.7, 69.05, 69.05, 78.7],
    ],
  );
});

test("calculateBrickIndicator keeps flat bars at zero when the high-low range is unavailable", () => {
  assert.deepEqual(
    calculateBrickIndicator([
      { close: 8, date: "2026-01-01", high: 8, low: 8 },
      { close: 8, date: "2026-01-02", high: 8, low: 8 },
    ]),
    [
      { date: "2026-01-01", rising: true, value: 0 },
      { date: "2026-01-02", rising: true, value: 0 },
    ],
  );
});

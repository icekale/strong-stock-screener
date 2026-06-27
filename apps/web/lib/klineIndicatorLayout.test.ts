import assert from "node:assert/strict";
import test from "node:test";

const {
  buildKlineIndicatorState,
  buildKlineIndicatorOptions,
  buildKlinePanes,
  KLINE_SUB_INDICATOR_OPTIONS,
} = (await import(new URL("./klineIndicatorLayout.ts", import.meta.url).href)) as typeof import("./klineIndicatorLayout");

test("kline sub indicator options include every supported secondary indicator", () => {
  assert.deepEqual(
    KLINE_SUB_INDICATOR_OPTIONS.map((item) => item.value),
    ["volume", "macd", "kdj", "rsi", "wr", "bias", "cci", "atr", "obv", "roc", "dmi", "brick"],
  );
  assert.ok(KLINE_SUB_INDICATOR_OPTIONS.some((item) => item.label === "砖形图" && item.value === "brick"));
});

test("kline indicator state normalizes pane count and fills sensible defaults", () => {
  assert.deepEqual(buildKlineIndicatorState({ paneCount: 1, subIndicators: [] }), {
    paneCount: 1,
    subIndicators: ["volume"],
  });
  assert.deepEqual(buildKlineIndicatorState({ paneCount: 2, subIndicators: ["rsi"] }), {
    paneCount: 2,
    subIndicators: ["rsi", "macd"],
  });
  assert.deepEqual(buildKlineIndicatorState({ paneCount: 3, subIndicators: ["wr", "bias", "cci"] }), {
    paneCount: 3,
    subIndicators: ["wr", "bias", "cci"],
  });
});

test("kline indicator state rejects invalid stored values", () => {
  assert.deepEqual(
    buildKlineIndicatorState({
      paneCount: 9,
      subIndicators: ["volume", "bad", "roc"],
    }),
    {
      paneCount: 1,
      subIndicators: ["volume"],
    },
  );
});

test("kline panes preserve selected sub indicators while chart indicators stay unique", () => {
  const state = buildKlineIndicatorState({ paneCount: 3, subIndicators: ["macd", "macd", "dmi"] });
  const panes = buildKlinePanes(["ma5", "ma20"], state.subIndicators);

  assert.deepEqual(state, {
    paneCount: 3,
    subIndicators: ["macd", "macd", "dmi"],
  });
  assert.deepEqual(panes.chartIndicators, ["ma", "macd", "dmi"]);
  assert.deepEqual(
    panes.panes.map((pane) => ({ id: pane.id, height: pane.height, indicators: pane.indicators })),
    [
      { id: "main", height: "52%", indicators: ["ma"] },
      { id: "sub_macd_0", height: "14%", indicators: ["macd"] },
      { id: "sub_macd_1", height: "14%", indicators: ["macd"] },
      { id: "sub_dmi_2", height: "14%", indicators: ["dmi"] },
    ],
  );
});

test("custom brick indicator gets an empty native pane and stays out of native chart indicators", () => {
  const state = buildKlineIndicatorState({ paneCount: 2, subIndicators: ["brick", "macd"] });
  const panes = buildKlinePanes(["ma5"], state.subIndicators);

  assert.deepEqual(state, {
    paneCount: 2,
    subIndicators: ["brick", "macd"],
  });
  assert.deepEqual(panes.chartIndicators, ["ma", "macd"]);
  assert.deepEqual(
    panes.panes.map((pane) => ({ id: pane.id, height: pane.height, indicators: pane.indicators })),
    [
      { id: "main", height: "62%", indicators: ["ma"] },
      { id: "sub_brick_0", height: "16%", indicators: [] },
      { id: "sub_macd_1", height: "16%", indicators: ["macd"] },
    ],
  );
});

test("kline indicator options only include selected moving average periods", () => {
  assert.deepEqual(buildKlineIndicatorOptions(["ma20"]).ma, { periods: [20], type: "sma" });
  assert.deepEqual(buildKlineIndicatorOptions(["ma60", "ma5"]).ma, { periods: [5, 60], type: "sma" });
  assert.deepEqual(buildKlineIndicatorOptions([]).ma, { periods: [], type: "sma" });
});

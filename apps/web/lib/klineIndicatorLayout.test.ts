import assert from "node:assert/strict";
import test from "node:test";

const {
  buildKlineIndicatorState,
  buildKlinePanes,
  KLINE_SUB_INDICATOR_OPTIONS,
} = (await import(new URL("./klineIndicatorLayout.ts", import.meta.url).href)) as typeof import("./klineIndicatorLayout");

test("kline sub indicator options include every supported secondary indicator", () => {
  assert.deepEqual(
    KLINE_SUB_INDICATOR_OPTIONS.map((item) => item.value),
    ["volume", "macd", "kdj", "rsi", "wr", "bias", "cci", "atr", "obv", "roc", "dmi"],
  );
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

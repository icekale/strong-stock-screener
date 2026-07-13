import assert from "node:assert/strict";
import test from "node:test";
import type { ChanlunAnalysisResponse } from "./types";

const {
  buildTickFlowOverlayOption,
} = (await import(new URL("./brickIndicator.ts", import.meta.url).href)) as typeof import("./brickIndicator");

const chanlun: ChanlunAnalysisResponse = {
  adjustment_mode: "raw_unadjusted",
  availability: "ready",
  bars: [],
  calculated_at: "2026-01-02T10:00:00+08:00",
  divergences: [],
  fractals: [],
  last_closed_bar_at: null,
  period: "5m",
  rule_version: "cl-v1",
  segments: [],
  signals: [],
  source_status: [],
  strokes: [],
  symbol: "600000.SH",
  zones: [
    {
      end_at: "2026-01-02T10:00:00+08:00",
      high: 11,
      id: "zone",
      low: 10,
      start_at: "2026-01-02T09:35:00+08:00",
      status: "confirmed",
      virtual: false,
    },
  ],
};

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

test("tickflow overlay series use stable ids to avoid merging into the base K-line series", () => {
  const option = buildTickFlowOverlayOption({
    annotations: [
      {
        date: "20260102",
        end_date: null,
        label: "B区A点",
        description: "结构确认",
        price: 10.8,
        severity: "positive",
        start_date: null,
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
  assert.deepEqual(
    series.map((item) => item.id),
    ["custom-gsgf-annotations", "custom-brick-0"],
  );
});

test("combined overlay keeps unique GSGF Chanlun and brick ids", () => {
  const option = buildTickFlowOverlayOption({
    annotations: [],
    chanlun,
    chanlunLayers: { fractals: false, segments: false, strokes: false, zones: true },
    chartData: [
      { amount: null, close: 10, date: "2026-01-01", high: 11, low: 9, open: 9.5, volume: 1000 },
    ],
    showGsgfAnnotations: false,
    subIndicators: ["brick"],
    visibleBarCount: 20,
  });
  const ids = (Array.isArray(option.series) ? option.series : []).map((item) => item.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.deepEqual(ids, ["chanlun-zones", "custom-brick-0"]);
});

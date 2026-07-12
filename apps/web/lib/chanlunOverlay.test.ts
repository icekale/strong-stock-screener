import assert from "node:assert/strict";
import test from "node:test";
import type { ChanlunAnalysisResponse } from "./types";

const { buildChanlunClearSeries, buildChanlunOverlaySeries, resolveVisibleBarCount } = (await import(
  new URL("./chanlunOverlay.ts", import.meta.url).href
)) as typeof import("./chanlunOverlay");

const analysis: ChanlunAnalysisResponse = {
  adjustment_mode: "raw_unadjusted",
  availability: "ready",
  bars: [],
  calculated_at: "2026-07-10T15:00:00+08:00",
  fractals: [],
  last_closed_bar_at: null,
  period: "5m",
  rule_version: "cl-v1",
  segments: [
    {
      direction: "up",
      end_at: "2026-07-10T10:00:00+08:00",
      end_price: 12,
      id: "segment",
      start_at: "2026-07-10T09:35:00+08:00",
      start_price: 10,
      status: "confirmed",
    },
  ],
  source_status: [],
  strokes: [
    {
      direction: "up",
      end_at: "2026-07-10T10:00:00+08:00",
      end_price: 12,
      id: "stroke",
      start_at: "2026-07-10T09:35:00+08:00",
      start_price: 10,
      status: "confirmed",
    },
  ],
  symbol: "600000.SH",
  zones: [
    {
      end_at: "2026-07-10T10:00:00+08:00",
      high: 12,
      id: "zone",
      low: 10,
      start_at: "2026-07-10T09:35:00+08:00",
      status: "confirmed",
      virtual: false,
    },
  ],
};

test("chanlun overlay uses stable zone stroke and segment ids", () => {
  const series = buildChanlunOverlaySeries(analysis, {
    fractals: false,
    segments: true,
    strokes: true,
    zones: true,
  });

  assert.deepEqual(series.map((item) => item.id), [
    "chanlun-zones",
    "chanlun-strokes",
    "chanlun-segments",
  ]);
});

test("chanlun overlay omits fractals while zoomed out", () => {
  const series = buildChanlunOverlaySeries(
    analysis,
    { fractals: true, segments: true, strokes: true, zones: true },
    { visibleBarCount: 180 },
  );

  assert.equal(series.some((item) => item.id === "chanlun-fractals"), false);
});

test("chanlun clear series covers every stable overlay id", () => {
  assert.deepEqual(buildChanlunClearSeries().map((item) => item.id), [
    "chanlun-zones",
    "chanlun-strokes",
    "chanlun-segments",
    "chanlun-fractals",
  ]);
});

test("visible range percentage resolves to actual bar count", () => {
  assert.equal(resolveVisibleBarCount(240, { end: 100, start: 25 }), 180);
});

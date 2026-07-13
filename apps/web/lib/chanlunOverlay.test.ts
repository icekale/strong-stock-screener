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
  assert.ok(series.every((item) => item.z === 20));
});

test("chanlun overlay omits fractals while zoomed out", () => {
  const series = buildChanlunOverlaySeries(
    analysis,
    { fractals: true, segments: true, strokes: true, zones: true },
    { visibleBarCount: 180 },
  );

  assert.equal(series.some((item) => item.id === "chanlun-fractals"), false);
});

test("chanlun overlay aligns structure timestamps to daily K-line categories", () => {
  const series = buildChanlunOverlaySeries(
    analysis,
    { fractals: false, segments: true, strokes: true, zones: true },
    { chartDates: ["2026-07-10"], visibleBarCount: 20 },
  );
  const strokes = series.find((item) => item.id === "chanlun-strokes");
  const zones = series.find((item) => item.id === "chanlun-zones");
  const strokeData = strokes?.data as Array<{ value: [string | null, number | null] }>;
  const zoneData = (zones?.markArea as { data: Array<Array<{ xAxis: string }>> }).data;

  assert.deepEqual(
    strokeData.map((item) => item.value[0]),
    ["2026-07-10", "2026-07-10", null],
  );
  assert.deepEqual(zoneData[0].map((item) => item.xAxis), ["2026-07-10", "2026-07-10"]);
});

test("chanlun overlay preserves exact intraday K-line categories", () => {
  const chartDates = ["2026-07-10T09:35:00+08:00", "2026-07-10T10:00:00+08:00"];
  const series = buildChanlunOverlaySeries(
    analysis,
    { fractals: false, segments: true, strokes: true, zones: true },
    { chartDates, visibleBarCount: 20 },
  );
  const strokes = series.find((item) => item.id === "chanlun-strokes");
  const zones = series.find((item) => item.id === "chanlun-zones");
  const strokeData = strokes?.data as Array<{ value: [string | null, number | null] }>;
  const zoneData = (zones?.markArea as { data: Array<Array<{ xAxis: string }>> }).data;

  assert.deepEqual(
    strokeData.map((item) => item.value[0]),
    [chartDates[0], chartDates[1], null],
  );
  assert.deepEqual(zoneData[0].map((item) => item.xAxis), chartDates);
});

test("chanlun clear series covers every stable overlay id", () => {
  assert.deepEqual(buildChanlunClearSeries().map((item) => item.id), [
    "chanlun-zones",
    "chanlun-strokes",
    "chanlun-segments",
    "chanlun-fractals",
  ]);
});

test("chanlun clear series leaves currently enabled layers intact", () => {
  assert.deepEqual(
    buildChanlunClearSeries(["chanlun-zones", "chanlun-segments"]).map((item) => item.id),
    ["chanlun-strokes", "chanlun-fractals"],
  );
});

test("visible range percentage resolves to actual bar count", () => {
  assert.equal(resolveVisibleBarCount(240, { end: 100, start: 25 }), 180);
});

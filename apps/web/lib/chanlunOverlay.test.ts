import assert from "node:assert/strict";
import test from "node:test";
import type { ChanlunAnalysisResponse } from "./types";

const {
  buildChanlunClearSeries,
  buildChanlunOverlaySeries,
  mergeChanlunSeries,
  resolveKlineOverlaySeries,
  resolveVisibleBarCount,
} = (await import(
  new URL("./chanlunOverlay.ts", import.meta.url).href
)) as typeof import("./chanlunOverlay");

const analysis: ChanlunAnalysisResponse = {
  adjustment_mode: "raw_unadjusted",
  availability: "ready",
  bars: [],
  calculated_at: "2026-07-10T15:00:00+08:00",
  divergences: [],
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
  signals: [],
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

test("chanlun overlay labels visible top and bottom fractals", () => {
  const series = buildChanlunOverlaySeries(
    {
      ...analysis,
      fractals: [
        { id: "top", mark: "top", occurred_at: "2026-07-10T09:35:00+08:00", price: 12, status: "confirmed" },
        { id: "bottom", mark: "bottom", occurred_at: "2026-07-10T10:00:00+08:00", price: 10, status: "confirmed" },
      ],
    },
    { fractals: true, segments: false, strokes: false, zones: false },
    { visibleBarCount: 20 },
  );
  const fractals = series.find((item) => item.id === "chanlun-fractals");
  const data = fractals?.data as Array<{ label: { formatter: string; show: boolean }; symbolRotate: number }>;

  assert.deepEqual(data.map((item) => item.label.formatter), ["顶", "底"]);
  assert.ok(data.every((item) => item.label.show));
  assert.deepEqual(data.map((item) => item.symbolRotate), [180, 0]);
});

test("chanlun overlay renders confirmed divergence references and one-buy markers from backend events", () => {
  const series = buildChanlunOverlaySeries(
    {
      ...analysis,
      divergences: [
        {
          coefficient: 0.42,
          current_macd_strength: 0.8,
          current_price: 9,
          current_stroke_id: "stroke-current",
          direction: "down",
          id: "divergence-bottom",
          occurred_at: "2026-07-10T10:00:00+08:00",
          reference_occurred_at: "2026-07-10T09:35:00+08:00",
          reference_macd_strength: 1.9,
          reference_price: 10,
          reference_stroke_id: "stroke-reference",
          rule_version: "cl-v1",
          status: "confirmed",
          type: "bottom",
          zone_count: 2,
        },
      ],
      signals: [
        {
          divergence_id: "divergence-bottom",
          id: "signal-one-buy",
          occurred_at: "2026-07-10T10:00:00+08:00",
          price: 9,
          rule_version: "cl-v1",
          status: "confirmed",
          stroke_id: "stroke-current",
          type: "one_buy",
        },
      ],
    } as ChanlunAnalysisResponse,
    { divergences: true, fractals: false, segments: false, signals: true, strokes: false, zones: false } as never,
    { visibleBarCount: 20 },
  );
  const divergences = series.find((item) => item.id === "chanlun-divergences");
  const signals = series.find((item) => item.id === "chanlun-signals");
  assert.ok(divergences);
  assert.ok(signals);
  const divergenceData = divergences?.data as Array<{ value: [string | null, number | null] }>;
  const signalData = signals?.data as Array<{ label: { formatter: string; show: boolean }; value: [string, number] }>;

  assert.deepEqual(divergenceData.map((item) => item.value), [
    ["2026-07-10 09:35", 10],
    ["2026-07-10 10:00", 9],
    [null, null],
  ]);
  assert.deepEqual(signalData.map((item) => item.value), [["2026-07-10 10:00", 9]]);
  assert.equal(signalData[0]?.label.formatter, "一买 0.42");
  assert.equal(signalData[0]?.label.show, true);
});

test("chanlun overlay labels second and third buy-sell points without assigning a divergence coefficient", () => {
  const series = buildChanlunOverlaySeries(
    {
      ...analysis,
      signals: [
        {
          divergence_id: null,
          id: "signal-two-buy",
          occurred_at: "2026-07-10T09:35:00+08:00",
          price: 10,
          rule_version: "cl-v1",
          status: "confirmed",
          stroke_id: "stroke-two-buy",
          type: "two_buy",
        },
        {
          divergence_id: null,
          id: "signal-three-sell",
          occurred_at: "2026-07-10T10:00:00+08:00",
          price: 12,
          rule_version: "cl-v1",
          status: "confirmed",
          stroke_id: "stroke-three-sell",
          type: "three_sell",
        },
      ],
    } as ChanlunAnalysisResponse,
    { divergences: false, fractals: false, segments: false, signals: true, strokes: false, zones: false } as never,
    { visibleBarCount: 20 },
  );
  const signals = series.find((item) => item.id === "chanlun-signals");
  assert.ok(signals);
  const data = signals?.data as Array<{ label: { formatter: string }; value: [string, number] }>;

  assert.deepEqual(data.map((item) => item.label.formatter), ["二买", "三卖"]);
  assert.deepEqual(data.map((item) => item.value), [
    ["2026-07-10 09:35", 10],
    ["2026-07-10 10:00", 12],
  ]);
});

test("chanlun overlay stacks nearby same-side signal labels and resets after a gap", () => {
  const chartDates = [
    "2026-07-10 09:30",
    "2026-07-10 09:35",
    "2026-07-10 09:40",
    "2026-07-10 09:45",
    "2026-07-10 09:50",
    "2026-07-10 09:55",
    "2026-07-10 10:00",
    "2026-07-10 10:05",
    "2026-07-10 10:10",
    "2026-07-10 10:15",
    "2026-07-10 10:20",
    "2026-07-10 10:25",
    "2026-07-10 10:30",
  ];
  const series = buildChanlunOverlaySeries(
    {
      ...analysis,
      signals: [
        { divergence_id: null, id: "sell-1", occurred_at: "2026-07-10T09:30:00+08:00", price: 12, rule_version: "cl-v1", status: "confirmed", stroke_id: "stroke-1", type: "one_sell" },
        { divergence_id: null, id: "sell-2", occurred_at: "2026-07-10T09:40:00+08:00", price: 12.2, rule_version: "cl-v1", status: "confirmed", stroke_id: "stroke-2", type: "two_sell" },
        { divergence_id: null, id: "sell-3", occurred_at: "2026-07-10T09:50:00+08:00", price: 12.1, rule_version: "cl-v1", status: "confirmed", stroke_id: "stroke-3", type: "three_sell" },
        { divergence_id: null, id: "buy-1", occurred_at: "2026-07-10T09:45:00+08:00", price: 10, rule_version: "cl-v1", status: "confirmed", stroke_id: "stroke-4", type: "one_buy" },
        { divergence_id: null, id: "sell-4", occurred_at: "2026-07-10T10:30:00+08:00", price: 12.4, rule_version: "cl-v1", status: "confirmed", stroke_id: "stroke-5", type: "one_sell" },
      ],
    },
    { divergences: false, fractals: false, segments: false, signals: true, strokes: false, zones: false },
    { chartDates, visibleBarCount: 20 },
  );
  const signals = series.find((item) => item.id === "chanlun-signals");
  const data = signals?.data as Array<{ label: { distance: number; position: string } }>;

  assert.deepEqual(data.map((item) => item.label.position), ["top", "top", "top", "bottom", "top"]);
  assert.deepEqual(data.map((item) => item.label.distance), [8, 22, 36, 8, 8]);
});

test("chanlun overlay renders confirmed and virtual central zones as labeled areas", () => {
  const series = buildChanlunOverlaySeries(
    {
      ...analysis,
      zones: [
        analysis.zones[0]!,
        { ...analysis.zones[0]!, id: "virtual-zone", virtual: true },
      ],
    },
    { fractals: false, segments: false, strokes: false, zones: true },
    { visibleBarCount: 20 },
  );
  const zones = series.find((item) => item.id === "chanlun-zones");
  const markArea = zones?.markArea as {
    data: Array<Array<{ itemStyle: { borderType: string }; name: string; xAxis: string; yAxis: number }>>;
    label: { formatter: string; show: boolean };
  };

  assert.deepEqual(markArea.data.map((area) => area[0]?.name), ["中枢", "虚中枢"]);
  assert.deepEqual(markArea.data[0]?.map((point) => point.xAxis), ["2026-07-10 09:35", "2026-07-10 10:00"]);
  assert.equal(markArea.data[1]?.[0]?.itemStyle.borderType, "dashed");
  assert.equal(markArea.label.formatter, "{b}");
  assert.equal(markArea.label.show, true);
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
  assert.deepEqual(zoneData[0]?.map((item) => item.xAxis), ["2026-07-10", "2026-07-10"]);
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
  assert.deepEqual(zoneData[0]?.map((item) => item.xAxis), chartDates);
});

test("chanlun clear series covers every stable overlay id", () => {
  assert.deepEqual(buildChanlunClearSeries().map((item) => item.id), [
    "chanlun-zones",
    "chanlun-strokes",
    "chanlun-segments",
    "chanlun-divergences",
    "chanlun-signals",
    "chanlun-fractals",
  ]);
});

test("chanlun clear series leaves currently enabled layers intact", () => {
  assert.deepEqual(
    buildChanlunClearSeries([
      "chanlun-zones",
      "chanlun-segments",
      "chanlun-divergences",
      "chanlun-signals",
    ]).map((item) => item.id),
    ["chanlun-strokes", "chanlun-fractals"],
  );
});

test("chanlun series merge preserves base K-line series and replaces stale Chanlun layers", () => {
  const baseSeries = [
    { id: "kline-candles", type: "candlestick" },
    { id: "ma-5", type: "line" },
    { data: ["stale"], id: "chanlun-zones", type: "line" },
  ];
  const overlays = buildChanlunOverlaySeries(
    analysis,
    { fractals: false, segments: true, strokes: false, zones: true },
    { visibleBarCount: 20 },
  );

  const merged = mergeChanlunSeries(baseSeries, overlays);

  assert.deepEqual(merged.map((item) => item.id), [
    "kline-candles",
    "ma-5",
    "chanlun-zones",
    "chanlun-segments",
  ]);
  assert.notDeepEqual(merged[2]?.data, ["stale"]);
});

test("chanlun series merge clears stale CZSC research markers", () => {
  const merged = mergeChanlunSeries(
    [
      { id: "kline-candles", type: "candlestick" },
      { data: ["stale"], id: "czsc-research-markers", type: "scatter" },
    ],
    [{ data: [], id: "czsc-research-markers", type: "scatter" }],
  );

  assert.deepEqual(merged.map((item) => item.id), ["kline-candles", "czsc-research-markers"]);
  assert.deepEqual(merged[1]?.data, []);
});

test("K-line overlays wait for a current base series snapshot", () => {
  const baseSeries = [
    { id: "kline-candles", type: "candlestick" },
    { id: "ma-5", type: "line" },
  ];
  const overlays = [{ id: "chanlun-strokes", type: "line" }];

  assert.equal(resolveKlineOverlaySeries(null, "300308.SZ|daily", overlays), undefined);
  assert.equal(
    resolveKlineOverlaySeries(
      { key: "300308.SZ|5", series: baseSeries },
      "300308.SZ|daily",
      overlays,
    ),
    undefined,
  );
  assert.deepEqual(
    resolveKlineOverlaySeries(
      { key: "300308.SZ|daily", series: baseSeries },
      "300308.SZ|daily",
      overlays,
    )?.map((item) => item.id),
    ["kline-candles", "ma-5", "chanlun-strokes"],
  );
});

test("visible range percentage resolves to actual bar count", () => {
  assert.equal(resolveVisibleBarCount(240, { end: 100, start: 25 }), 180);
});

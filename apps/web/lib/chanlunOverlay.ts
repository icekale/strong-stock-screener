import type {
  ChanlunAnalysisResponse,
  ChanlunDirection,
  ChanlunLayerKey,
  ChanlunStroke,
} from "./types";

type ChanlunOverlaySeries = Record<string, unknown> & { id: string };
type ChanlunLayers = Record<ChanlunLayerKey, boolean>;

const FRACTAL_TOP_COLOR = "#d9363e";
const FRACTAL_BOTTOM_COLOR = "#07845e";
const STROKE_COLORS: Record<ChanlunDirection, string> = {
  down: "#07845e",
  unknown: "#64748b",
  up: "#d9363e",
};
const SEGMENT_COLORS: Record<ChanlunDirection, string> = {
  down: "#6d28d9",
  unknown: "#64748b",
  up: "#0f4cbb",
};

export function buildChanlunOverlaySeries(
  analysis: ChanlunAnalysisResponse,
  layers: ChanlunLayers,
  options: { chartDates?: readonly string[]; visibleBarCount?: number } = {},
): ChanlunOverlaySeries[] {
  const series: ChanlunOverlaySeries[] = [];

  if (layers.zones && analysis.zones.length > 0) {
    series.push(buildZoneSeries(analysis, options.chartDates));
  }
  if (layers.strokes && analysis.strokes.length > 0) {
    series.push(buildStrokeSeries("chanlun-strokes", "缠论笔", analysis.strokes, STROKE_COLORS, 1, options.chartDates));
  }
  if (layers.segments && analysis.segments.length > 0) {
    series.push(buildStrokeSeries("chanlun-segments", "缠论线段", analysis.segments, SEGMENT_COLORS, 3, options.chartDates));
  }
  if (layers.fractals && (options.visibleBarCount ?? 0) <= 120 && analysis.fractals.length > 0) {
    series.push({
      data: analysis.fractals.map((item) => ({
        itemStyle: { color: item.mark === "top" ? FRACTAL_TOP_COLOR : FRACTAL_BOTTOM_COLOR },
        value: [resolveChartDate(item.occurred_at, options.chartDates), item.price],
      })),
      id: "chanlun-fractals",
      name: "缠论分型",
      silent: true,
      symbol: "circle",
      symbolSize: 6,
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
      z: 20,
    });
  }

  return series;
}

export function buildChanlunClearSeries(activeLayerIds: readonly string[] = []): ChanlunOverlaySeries[] {
  return [
    { data: [], id: "chanlun-zones", markArea: { data: [] }, type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-strokes", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-segments", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-fractals", type: "scatter", xAxisIndex: 0, yAxisIndex: 0 },
  ].filter((series) => !activeLayerIds.includes(series.id));
}

export function resolveVisibleBarCount(totalBars: number, range: { start: number; end: number }): number {
  return Math.max(0, Math.ceil(totalBars * (range.end - range.start) / 100));
}

function buildZoneSeries(analysis: ChanlunAnalysisResponse, chartDates?: readonly string[]): ChanlunOverlaySeries {
  return {
    data: [],
    id: "chanlun-zones",
    markArea: {
      data: analysis.zones.map((zone) => [
        {
          itemStyle: {
            borderColor: zone.virtual ? "rgba(124,58,237,0.48)" : "rgba(23,105,224,0.56)",
            borderType: zone.virtual ? "dashed" : "solid",
            color: zone.virtual ? "rgba(124,58,237,0.04)" : "rgba(23,105,224,0.08)",
          },
          xAxis: resolveChartDate(zone.start_at, chartDates),
          yAxis: zone.low,
        },
        { xAxis: resolveChartDate(zone.end_at, chartDates), yAxis: zone.high },
      ]),
      silent: true,
    },
    name: "缠论中枢",
    silent: true,
    type: "line",
    xAxisIndex: 0,
    yAxisIndex: 0,
    z: 20,
  };
}

function buildStrokeSeries(
  id: string,
  name: string,
  strokes: ChanlunStroke[],
  colors: Record<ChanlunDirection, string>,
  width: number,
  chartDates?: readonly string[],
): ChanlunOverlaySeries {
  return {
    data: strokes.flatMap((stroke) => [
      { value: [resolveChartDate(stroke.start_at, chartDates), stroke.start_price] },
      {
        lineStyle: { color: colors[stroke.direction], type: "solid", width },
        value: [resolveChartDate(stroke.end_at, chartDates), stroke.end_price],
      },
      { value: [null, null] },
    ]),
    id,
    lineStyle: { color: colors.unknown, type: "solid", width },
    name,
    silent: true,
    showSymbol: false,
    type: "line",
    xAxisIndex: 0,
    yAxisIndex: 0,
    z: 20,
  };
}

function resolveChartDate(value: string, chartDates?: readonly string[]): string {
  const normalized = normalizeDate(value);
  if (!chartDates?.length) {
    return normalized;
  }

  const exact = chartDates.find((date) => normalizeDate(date) === normalized);
  if (exact) {
    return exact;
  }

  const sameDay = chartDates.filter((date) => normalizeDate(date).slice(0, 10) === normalized.slice(0, 10));
  return sameDay.length === 1 ? sameDay[0] : normalized;
}

function normalizeDate(value: string): string {
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value.replace("T", " ").replace(/(?:[+-]\d{2}:?\d{2}|Z)$/, "").slice(0, 16);
}

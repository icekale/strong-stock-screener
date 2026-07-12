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
  down: "#7c3aed",
  unknown: "#64748b",
  up: "#1769e0",
};

export function buildChanlunOverlaySeries(
  analysis: ChanlunAnalysisResponse,
  layers: ChanlunLayers,
  options: { visibleBarCount?: number } = {},
): ChanlunOverlaySeries[] {
  const series: ChanlunOverlaySeries[] = [];

  if (layers.zones && analysis.zones.length > 0) {
    series.push(buildZoneSeries(analysis));
  }
  if (layers.strokes && analysis.strokes.length > 0) {
    series.push(buildStrokeSeries("chanlun-strokes", "缠论笔", analysis.strokes, STROKE_COLORS, 1));
  }
  if (layers.segments && analysis.segments.length > 0) {
    series.push(buildStrokeSeries("chanlun-segments", "缠论线段", analysis.segments, SEGMENT_COLORS, 3));
  }
  if (layers.fractals && (options.visibleBarCount ?? 0) <= 120 && analysis.fractals.length > 0) {
    series.push({
      data: analysis.fractals.map((item) => ({
        itemStyle: { color: item.mark === "top" ? FRACTAL_TOP_COLOR : FRACTAL_BOTTOM_COLOR },
        value: [normalizeDate(item.occurred_at), item.price],
      })),
      id: "chanlun-fractals",
      name: "缠论分型",
      silent: true,
      symbol: "circle",
      symbolSize: 6,
      type: "scatter",
      xAxisIndex: 0,
      yAxisIndex: 0,
    });
  }

  return series;
}

export function buildChanlunClearSeries(): ChanlunOverlaySeries[] {
  return [
    { data: [], id: "chanlun-zones", markArea: { data: [] }, type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-strokes", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-segments", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-fractals", type: "scatter", xAxisIndex: 0, yAxisIndex: 0 },
  ];
}

export function resolveVisibleBarCount(totalBars: number, range: { start: number; end: number }): number {
  return Math.max(0, Math.ceil(totalBars * (range.end - range.start) / 100));
}

function buildZoneSeries(analysis: ChanlunAnalysisResponse): ChanlunOverlaySeries {
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
          xAxis: normalizeDate(zone.start_at),
          yAxis: zone.low,
        },
        { xAxis: normalizeDate(zone.end_at), yAxis: zone.high },
      ]),
      silent: true,
    },
    name: "缠论中枢",
    silent: true,
    type: "line",
    xAxisIndex: 0,
    yAxisIndex: 0,
  };
}

function buildStrokeSeries(
  id: string,
  name: string,
  strokes: ChanlunStroke[],
  colors: Record<ChanlunDirection, string>,
  width: number,
): ChanlunOverlaySeries {
  return {
    data: strokes.flatMap((stroke) => [
      { value: [normalizeDate(stroke.start_at), stroke.start_price] },
      {
        lineStyle: { color: colors[stroke.direction], type: "solid", width },
        value: [normalizeDate(stroke.end_at), stroke.end_price],
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
  };
}

function normalizeDate(value: string): string {
  return value.replace("T", " ").slice(0, 16);
}

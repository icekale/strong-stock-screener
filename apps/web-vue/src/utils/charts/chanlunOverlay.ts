import type {
  ChanlunAnalysisResponse,
  ChanlunDirection,
  ChanlunLayerKey,
  ChanlunSignalType,
  ChanlunStroke,
} from "@/service/types";

type ChanlunOverlaySeries = Record<string, unknown> & { id: string };
type ChanlunLayers = Partial<Record<ChanlunLayerKey, boolean>>;
export type EchartsSeries = Record<string, unknown>;
export type KlineSeriesSnapshot = {
  key: string;
  series: readonly EchartsSeries[];
};

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
const BUY_SIGNAL_COLOR = "#07845e";
const SELL_SIGNAL_COLOR = "#d9363e";
const SIGNAL_LABEL_BASE_DISTANCE = 8;
const SIGNAL_LABEL_LANE_GAP = 14;
const SIGNAL_LABEL_COLLISION_WINDOW = 8;

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
  if (layers.divergences && analysis.divergences.length > 0) {
    series.push(buildDivergenceSeries(analysis, options.chartDates));
  }
  if (layers.signals && analysis.signals.length > 0) {
    series.push(buildSignalSeries(analysis, options.chartDates, options.visibleBarCount));
  }
  if (layers.fractals && (options.visibleBarCount ?? 0) <= 120 && analysis.fractals.length > 0) {
    series.push({
      data: analysis.fractals.map((item) => ({
        itemStyle: { color: item.mark === "top" ? FRACTAL_TOP_COLOR : FRACTAL_BOTTOM_COLOR },
        label: {
          color: item.mark === "top" ? FRACTAL_TOP_COLOR : FRACTAL_BOTTOM_COLOR,
          fontSize: 11,
          fontWeight: 700,
          formatter: item.mark === "top" ? "顶" : "底",
          position: item.mark === "top" ? "top" : "bottom",
          show: true,
        },
        symbolRotate: item.mark === "top" ? 180 : 0,
        value: [resolveChartDate(item.occurred_at, options.chartDates), item.price],
      })),
      id: "chanlun-fractals",
      name: "缠论分型",
      silent: true,
      symbol: "triangle",
      symbolSize: 8,
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
    { data: [], id: "chanlun-zones", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-strokes", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-segments", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-divergences", type: "line", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-signals", type: "scatter", xAxisIndex: 0, yAxisIndex: 0 },
    { data: [], id: "chanlun-fractals", type: "scatter", xAxisIndex: 0, yAxisIndex: 0 },
  ].filter((series) => !activeLayerIds.includes(series.id));
}

export function mergeChanlunSeries(
  baseSeries: readonly EchartsSeries[],
  chanlunSeries: readonly EchartsSeries[],
): EchartsSeries[] {
  return [
    ...baseSeries.filter((series) => !isManagedOverlaySeriesId(series.id)),
    ...chanlunSeries,
  ];
}

export function resolveKlineOverlaySeries(
  baseSnapshot: KlineSeriesSnapshot | null,
  chartKey: string,
  overlaySeries: readonly EchartsSeries[],
): EchartsSeries[] | undefined {
  if (!baseSnapshot || baseSnapshot.key !== chartKey) {
    return undefined;
  }
  return mergeChanlunSeries(baseSnapshot.series, overlaySeries);
}

export function resolveVisibleBarCount(totalBars: number, range: { start: number; end: number }): number {
  return Math.max(0, Math.ceil(totalBars * (range.end - range.start) / 100));
}

function buildDivergenceSeries(
  analysis: ChanlunAnalysisResponse,
  chartDates?: readonly string[],
): ChanlunOverlaySeries {
  return {
    data: analysis.divergences.flatMap((divergence) => [
      { value: [resolveChartDate(divergence.reference_occurred_at, chartDates), divergence.reference_price] },
      {
        lineStyle: { color: divergenceColor(divergence.type), type: "dashed", width: 1.5 },
        value: [resolveChartDate(divergence.occurred_at, chartDates), divergence.current_price],
      },
      { value: [null, null] },
    ]),
    id: "chanlun-divergences",
    lineStyle: { color: "#64748b", type: "dashed", width: 1.5 },
    name: "缠论背驰",
    silent: true,
    showSymbol: false,
    type: "line",
    xAxisIndex: 0,
    yAxisIndex: 0,
    z: 20,
  };
}

function buildSignalSeries(
  analysis: ChanlunAnalysisResponse,
  chartDates: readonly string[] | undefined,
  visibleBarCount: number | undefined,
): ChanlunOverlaySeries {
  const divergencesById = new Map(analysis.divergences.map((item) => [item.id, item]));
  const showLabels = (visibleBarCount ?? 0) <= 120;
  const labelDistances = resolveSignalLabelDistances(analysis.signals, chartDates);
  return {
    data: analysis.signals.map((signal, index) => {
      const divergence = signal.divergence_id ? divergencesById.get(signal.divergence_id) : undefined;
      const isBuy = signal.type.endsWith("buy");
      return {
        itemStyle: { color: isBuy ? BUY_SIGNAL_COLOR : SELL_SIGNAL_COLOR },
        label: {
          color: isBuy ? BUY_SIGNAL_COLOR : SELL_SIGNAL_COLOR,
          distance: labelDistances[index],
          fontSize: 11,
          fontWeight: 700,
          formatter: `${signalLabel(signal.type)}${divergence ? ` ${divergence.coefficient.toFixed(2)}` : ""}`,
          position: isBuy ? "bottom" : "top",
          show: showLabels,
        },
        symbolRotate: isBuy ? 0 : 180,
        value: [resolveChartDate(signal.occurred_at, chartDates), signal.price],
      };
    }),
    id: "chanlun-signals",
    name: "缠论买卖点",
    silent: true,
    symbol: "triangle",
    symbolSize: 10,
    type: "scatter",
    xAxisIndex: 0,
    yAxisIndex: 0,
    z: 20,
  };
}

function resolveSignalLabelDistances(
  signals: ChanlunAnalysisResponse["signals"],
  chartDates: readonly string[] | undefined,
): number[] {
  const distances = Array.from({ length: signals.length }, () => SIGNAL_LABEL_BASE_DISTANCE);
  const activeLanes: Record<"buy" | "sell", Array<{ barIndex: number; lane: number }>> = { buy: [], sell: [] };
  const sortedSignals = signals
    .map((signal, index) => ({
      barIndex: resolveSignalBarIndex(signal.occurred_at, chartDates, index),
      index,
      side: (signal.type.endsWith("buy") ? "buy" : "sell") as "buy" | "sell",
    }))
    .sort((left, right) => left.barIndex - right.barIndex || left.index - right.index);

  for (const signal of sortedSignals) {
    const nearby = activeLanes[signal.side].filter(
      (previous) => signal.barIndex - previous.barIndex <= SIGNAL_LABEL_COLLISION_WINDOW,
    );
    const occupiedLanes = new Set(nearby.map((previous) => previous.lane));
    let lane = 0;
    while (occupiedLanes.has(lane)) {
      lane += 1;
    }
    nearby.push({ barIndex: signal.barIndex, lane });
    activeLanes[signal.side] = nearby;
    distances[signal.index] = SIGNAL_LABEL_BASE_DISTANCE + lane * SIGNAL_LABEL_LANE_GAP;
  }

  return distances;
}

function resolveSignalBarIndex(value: string, chartDates: readonly string[] | undefined, fallback: number): number {
  if (!chartDates?.length) {
    return fallback;
  }
  const chartDate = resolveChartDate(value, chartDates);
  const index = chartDates.indexOf(chartDate);
  return index === -1 ? fallback : index;
}

function buildZoneSeries(analysis: ChanlunAnalysisResponse, chartDates?: readonly string[]): ChanlunOverlaySeries {
  return {
    data: [],
    id: "chanlun-zones",
    markArea: {
      data: analysis.zones.map((zone) => [
        {
          itemStyle: {
            borderColor: zone.virtual ? "rgba(124,58,237,0.62)" : "rgba(23,105,224,0.72)",
            borderType: zone.virtual ? "dashed" : "solid",
            color: zone.virtual ? "rgba(124,58,237,0.08)" : "rgba(23,105,224,0.14)",
          },
          name: zone.virtual ? "虚中枢" : "中枢",
          xAxis: resolveChartDate(zone.start_at, chartDates),
          yAxis: zone.low,
        },
        { xAxis: resolveChartDate(zone.end_at, chartDates), yAxis: zone.high },
      ]),
      label: {
        color: "#0f4cbb",
        fontSize: 10,
        fontWeight: 700,
        formatter: "{b}",
        position: "insideTopLeft",
        show: true,
      },
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

function isManagedOverlaySeriesId(id: unknown): boolean {
  return typeof id === "string" && (id.startsWith("chanlun-") || id === "czsc-research-markers");
}

export function resolveChartDate(value: string, chartDates?: readonly string[]): string {
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

function divergenceColor(type: ChanlunAnalysisResponse["divergences"][number]["type"]): string {
  if (type === "bottom") {
    return BUY_SIGNAL_COLOR;
  }
  if (type === "top") {
    return SELL_SIGNAL_COLOR;
  }
  return "#b45309";
}

function signalLabel(type: ChanlunSignalType): string {
  return {
    one_buy: "一买",
    one_sell: "一卖",
    two_buy: "二买",
    two_sell: "二卖",
    three_buy: "三买",
    three_sell: "三卖",
  }[type];
}

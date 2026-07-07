import type { EChartsOption } from "echarts";
import type { CandlestickSeriesOption } from "echarts/charts";
import type { KlineData } from "kline-charts-react";
import type { KlineSubIndicator } from "./klineIndicatorLayout";
import type { GsgfChartAnnotation } from "./types";

const BRICK_UP_COLOR = "#f43f5e";
const BRICK_DOWN_COLOR = "#10b981";

export type BrickIndicatorBar = {
  close: number;
  date: string;
  high: number;
  low: number;
};

export type BrickIndicatorPoint = {
  date: string;
  rising: boolean;
  value: number;
};

export type BrickIndicatorSeries = CandlestickSeriesOption & {
  data: Array<{
    value: [number, number, number, number];
  }>;
  id: string;
  name: "砖形图";
  type: "candlestick";
  xAxisIndex: number;
  yAxisIndex: number;
};

export function calculateBrickIndicator(bars: BrickIndicatorBar[]): BrickIndicatorPoint[] {
  let var2aSma: number | null = null;
  let var4aSma: number | null = null;
  let var5aSma: number | null = null;
  const values: number[] = [];

  return bars.map((bar, index) => {
    const { highestHigh, lowestLow } = highestHighLowestLow(bars, index, 4);
    const range = highestHigh - lowestLow;
    const var1a = range > 0 ? ((highestHigh - bar.close) / range) * 100 - 90 : 0;
    var2aSma = tonghuashunSma(var1a, 4, var2aSma);
    const var2a = var2aSma + 100;

    const var3a = range > 0 ? ((bar.close - lowestLow) / range) * 100 : 0;
    var4aSma = tonghuashunSma(var3a, 6, var4aSma);
    var5aSma = tonghuashunSma(var4aSma, 6, var5aSma);
    const var5a = var5aSma + 100;
    const var6a = var5a - var2a;
    const value = var6a > 4 ? var6a - 4 : 0;
    const previousValue = values[index - 1] ?? value;
    values.push(value);

    return {
      date: bar.date,
      rising: index === 0 || value >= previousValue,
      value,
    };
  });
}

export function buildBrickIndicatorSeries(
  points: BrickIndicatorPoint[],
  subIndicators: KlineSubIndicator[],
): BrickIndicatorSeries[] {
  return subIndicators.flatMap((indicator, index) => {
    if (indicator !== "brick") {
      return [];
    }
    const axisIndex = index + 1;
    return [
      {
        barWidth: "55%",
        data: points.map((point, pointIndex) => {
          const previousValue = points[pointIndex - 1]?.value ?? point.value;
          return {
            value: [
              previousValue,
              point.value,
              Math.min(previousValue, point.value),
              Math.max(previousValue, point.value),
            ],
          };
        }),
        emphasis: { focus: "series" },
        id: `custom-brick-${index}`,
        itemStyle: {
          borderColor: BRICK_UP_COLOR,
          borderColor0: BRICK_DOWN_COLOR,
          borderWidth: 1,
          color: BRICK_UP_COLOR,
          color0: BRICK_DOWN_COLOR,
        },
        markLine: {
          data: [{ name: "红持绿空", yAxis: 0 }],
          label: {
            color: BRICK_DOWN_COLOR,
            formatter: "红持绿空",
            fontSize: 10,
            fontWeight: 700,
          },
          lineStyle: { color: BRICK_DOWN_COLOR, type: "solid", width: 1 },
          silent: true,
          symbol: "none",
        },
        name: "砖形图",
        type: "candlestick",
        xAxisIndex: axisIndex,
        yAxisIndex: axisIndex,
      },
    ];
  });
}

export function buildTickFlowOverlayOption({
  annotations,
  chartData,
  showGsgfAnnotations,
  subIndicators,
}: {
  annotations: GsgfChartAnnotation[];
  chartData: KlineData[];
  showGsgfAnnotations: boolean;
  subIndicators: KlineSubIndicator[];
}): EChartsOption {
  const brickPoints = calculateBrickIndicator(
    chartData
      .filter(hasBrickIndicatorPrices)
      .map((bar) => ({
        close: bar.close,
        date: bar.date,
        high: bar.high,
        low: bar.low,
      })),
  );
  const brickSeries = buildBrickIndicatorSeries(brickPoints, subIndicators);
  const enabled = showGsgfAnnotations ? annotations : [];
  const points = enabled
    .filter((item) => item.date && item.price !== null && item.price !== undefined)
    .map((item) => ({
      coord: [normalizeKlineDate(item.date!), item.price],
      itemStyle: { color: annotationColor(item.severity) },
      label: {
        backgroundColor: annotationColor(item.severity),
        borderRadius: 3,
        color: "#ffffff",
        fontSize: 11,
        fontWeight: 700,
        padding: [3, 5],
      },
      name: item.label,
      value: item.label,
    }));
  const ranges = enabled
    .filter((item) => item.start_date && item.end_date)
    .map((item) => [
      {
        itemStyle: { color: annotationAreaColor(item.severity) },
        name: item.label,
        xAxis: normalizeKlineDate(item.start_date!),
      },
      {
        xAxis: normalizeKlineDate(item.end_date!),
      },
    ]);
  const annotationSeries =
    points.length > 0 || ranges.length > 0
      ? [
          {
            data: [],
            id: "custom-gsgf-annotations",
            markArea: { data: ranges, silent: true },
            markPoint: {
              data: points,
              label: { formatter: "{b}" },
              symbol: "pin",
              symbolSize: 52,
            },
            name: "GSGF标注",
            type: "candlestick",
            xAxisIndex: 0,
            yAxisIndex: 0,
          },
        ]
      : [];
  const series = [...annotationSeries, ...brickSeries];

  return series.length > 0 ? ({ series } as EChartsOption) : {};
}

function tonghuashunSma(value: number, period: number, previous: number | null): number {
  if (previous === null) {
    return value;
  }
  return (value + (period - 1) * previous) / period;
}

function highestHighLowestLow(
  bars: BrickIndicatorBar[],
  index: number,
  period: number,
): { highestHigh: number; lowestLow: number } {
  const start = Math.max(0, index - period + 1);
  let highestHigh = bars[start]?.high ?? 0;
  let lowestLow = bars[start]?.low ?? 0;

  for (let cursor = start + 1; cursor <= index; cursor += 1) {
    const bar = bars[cursor];
    highestHigh = Math.max(highestHigh, bar.high);
    lowestLow = Math.min(lowestLow, bar.low);
  }

  return { highestHigh, lowestLow };
}

function hasBrickIndicatorPrices(
  bar: KlineData,
): bar is KlineData & { close: number; high: number; low: number } {
  return bar.close !== null && bar.high !== null && bar.low !== null;
}

function annotationColor(severity: GsgfChartAnnotation["severity"]): string {
  if (severity === "positive") {
    return "#f43f5e";
  }
  if (severity === "warning") {
    return "#f59e0b";
  }
  if (severity === "danger") {
    return "#0f766e";
  }
  return "#64748b";
}

function annotationAreaColor(severity: GsgfChartAnnotation["severity"]): string {
  if (severity === "positive") {
    return "rgba(244, 63, 94, 0.07)";
  }
  if (severity === "warning") {
    return "rgba(245, 158, 11, 0.09)";
  }
  if (severity === "danger") {
    return "rgba(15, 118, 110, 0.08)";
  }
  return "rgba(100, 116, 139, 0.07)";
}

function normalizeKlineDate(value: string): string {
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}

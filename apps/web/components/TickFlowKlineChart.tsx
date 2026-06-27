"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EChartsOption } from "echarts";
import type { ForwardRefExoticComponent, RefAttributes } from "react";
import type {
  IndicatorOptions,
  KLineChartProps,
  KLineChartRef,
  KlineData,
  KLineDataProvider,
  ThemeConfig,
} from "kline-charts-react";
import { buildKlinePanes, type KlineSubIndicator } from "../lib/klineIndicatorLayout";
import type { GsgfChartAnnotation, KlineBar } from "../lib/types";

const ReactKLineChart = dynamic(
  () => import("kline-charts-react").then((module) => module.KLineChart),
  {
    loading: () => (
      <div className="flex h-full min-h-[460px] items-center justify-center bg-white text-sm font-bold text-slate-500">
        正在加载 K 线图...
      </div>
    ),
    ssr: false,
  },
) as ForwardRefExoticComponent<KLineChartProps & RefAttributes<KLineChartRef>>;

type MovingAverageField = "ma5" | "ma10" | "ma20" | "ma60";

const KLINE_THEME: ThemeConfig = {
  activeColor: "#0f172a",
  areaColor: "rgba(15, 23, 42, 0.06)",
  backgroundColor: "#ffffff",
  bollColors: ["#f59e0b", "#1683ff", "#8b5cf6"],
  crosshairColor: "#64748b",
  downColor: "#10b981",
  gridLineColor: "#e5e7eb",
  kcColors: ["#10b981", "#14b8a6", "#ec4899"],
  maColors: ["#1683ff", "#f59e0b", "#8b5cf6", "#64748b"],
  splitLineColor: "#eef2f7",
  textColor: "#0f172a",
  textColorSecondary: "#64748b",
  tooltipBgColor: "rgba(255,255,255,0.98)",
  tooltipBorderColor: "#cbd5e1",
  upColor: "#f43f5e",
  volumeDownColor: "#10b981",
  volumeUpColor: "#f43f5e",
};

const KLINE_INDICATOR_OPTIONS: IndicatorOptions = {
  ma: { periods: [5, 10, 20, 60], type: "sma" },
  macd: { short: 12, long: 26, signal: 9 },
  kdj: { dPeriod: 3, kPeriod: 3, period: 9 },
  rsi: { periods: [6, 12, 24] },
  wr: { periods: [6, 10] },
  bias: { periods: [6, 12, 24] },
  cci: { period: 14 },
  atr: { period: 14 },
  obv: { maPeriod: 30 },
  roc: { period: 12, signalPeriod: 6 },
  dmi: { adxPeriod: 6, period: 14 },
};

export function TickFlowKlineChart({
  annotations,
  bars,
  height,
  movingAverages,
  period,
  showGsgfAnnotations,
  subIndicators,
  symbol,
}: {
  annotations: GsgfChartAnnotation[];
  bars: KlineBar[];
  height: number;
  movingAverages: MovingAverageField[];
  period: "daily" | "weekly";
  showGsgfAnnotations: boolean;
  subIndicators: KlineSubIndicator[];
  symbol: string;
}) {
  const chartRef = useRef<KLineChartRef>(null);
  const [chartDataVersion, setChartDataVersion] = useState(0);
  const handleDataLoad = useCallback(() => {
    setChartDataVersion((version) => version + 1);
  }, []);
  const chartData = useMemo(() => convertBarsForKlineChart(bars, symbol), [bars, symbol]);
  const dataProvider = useMemo<KLineDataProvider>(
    () => ({
      getKline: async () => chartData,
    }),
    [chartData],
  );
  const requestOptions = useMemo(() => ({ abortOnChange: true, debounceMs: 0, dedupe: false }), []);
  const indicatorLayout = useMemo(
    () => buildKlinePanes(movingAverages, subIndicators),
    [movingAverages, subIndicators],
  );
  const echartsOption = useMemo(
    () => buildTickFlowAnnotationOption(annotations, showGsgfAnnotations),
    [annotations, showGsgfAnnotations],
  );

  useEffect(() => {
    const instance = chartRef.current?.getEchartsInstance();
    if (!instance) {
      return;
    }
    instance.setOption(echartsOption, false);
  }, [chartDataVersion, echartsOption, indicatorLayout]);

  if (bars.length === 0) {
    return (
      <div className="flex min-h-[460px] items-center justify-center bg-slate-50 text-sm font-bold text-slate-500">
        暂无 K 线数据
      </div>
    );
  }

  return (
    <div className="tickflow-kline-chart h-full min-h-[460px] bg-white">
      <ReactKLineChart
        ref={chartRef}
        adjust="qfq"
        dataProvider={dataProvider}
        height={height}
        indicatorOptions={KLINE_INDICATOR_OPTIONS}
        indicators={indicatorLayout.chartIndicators}
        market="A"
        maxSubPanes={subIndicators.length}
        onDataLoad={handleDataLoad}
        panes={indicatorLayout.panes}
        period={period}
        requestOptions={requestOptions}
        showIndicatorSelector={false}
        showPeriodSelector={false}
        showToolbar
        symbol={symbol}
        theme={KLINE_THEME}
        visibleCount={120}
        width="100%"
      />
    </div>
  );
}

export function convertBarsForKlineChart(bars: KlineBar[], symbol: string): KlineData[] {
  return bars.map((bar, index) => {
    const previous = bars[index - 1];
    const change = previous ? bar.close - previous.close : null;
    const changePercent = previous && previous.close !== 0 ? (change! / previous.close) * 100 : null;
    return {
      amount: null,
      change,
      changePercent,
      close: bar.close,
      code: symbol,
      date: normalizeKlineDate(bar.date),
      high: bar.high,
      low: bar.low,
      open: bar.open,
      volume: bar.volume,
    };
  });
}

function buildTickFlowAnnotationOption(
  annotations: GsgfChartAnnotation[],
  showGsgfAnnotations: boolean,
): EChartsOption {
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

  const klineSeries = {
    markArea: { data: ranges, silent: true },
    markPoint: {
      data: points,
      label: { formatter: "{b}" },
      symbol: "pin",
      symbolSize: 52,
    },
    name: "K线",
  };

  return {
    series: [klineSeries] as EChartsOption["series"],
  };
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

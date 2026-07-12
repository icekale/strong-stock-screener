"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ForwardRefExoticComponent, RefAttributes } from "react";
import type {
  KLineChartProps,
  KLineChartRef,
  KlineData,
  KLineDataProvider,
  ThemeConfig,
} from "kline-charts-react";
import {
  buildKlineIndicatorOptions,
  buildKlinePanes,
  type KlineMovingAverage,
  type KlineSubIndicator,
} from "../lib/klineIndicatorLayout";
import { buildTickFlowOverlayOption } from "../lib/brickIndicator";
import type { ChanlunAnalysisResponse, ChanlunLayerKey, GsgfChartAnnotation, KlineBar } from "../lib/types";

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

export type KlineChartDataSourceMode = "tickflow";

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

export function TickFlowKlineChart({
  annotations,
  bars,
  chanlun,
  chanlunLayers,
  dataSourceMode = "tickflow",
  height,
  movingAverages,
  period,
  showGsgfAnnotations,
  subIndicators,
  symbol,
}: {
  annotations: GsgfChartAnnotation[];
  bars: KlineBar[];
  chanlun?: ChanlunAnalysisResponse | null;
  chanlunLayers?: Record<ChanlunLayerKey, boolean>;
  dataSourceMode?: KlineChartDataSourceMode;
  height: number;
  movingAverages: KlineMovingAverage[];
  period: "daily" | "weekly";
  showGsgfAnnotations: boolean;
  subIndicators: KlineSubIndicator[];
  symbol: string;
}) {
  const chartRef = useRef<KLineChartRef>(null);
  const [chartDataVersion, setChartDataVersion] = useState(0);
  const handleDataLoad = useCallback((data: KlineData[]) => {
    setChartDataVersion((version) => version + 1);
  }, []);
  const chartData = useMemo(() => convertBarsForKlineChart(bars, symbol), [bars, symbol]);
  const tickflowDataProvider = useMemo<KLineDataProvider>(
    () => ({
      getKline: async () => chartData,
    }),
    [chartData],
  );
  const requestOptions = useMemo(() => ({ abortOnChange: true, debounceMs: 0, dedupe: false }), []);
  const indicatorOptions = useMemo(() => buildKlineIndicatorOptions(movingAverages), [movingAverages]);
  const indicatorLayout = useMemo(
    () => buildKlinePanes(movingAverages, subIndicators),
    [movingAverages, subIndicators],
  );
  const echartsOption = useMemo(
    () =>
      buildTickFlowOverlayOption({
        annotations,
        chanlun,
        chanlunLayers,
        chartData,
        showGsgfAnnotations: dataSourceMode === "tickflow" && showGsgfAnnotations,
        subIndicators,
        visibleBarCount: 120,
      }),
    [annotations, chanlun, chanlunLayers, chartData, dataSourceMode, showGsgfAnnotations, subIndicators],
  );

  useEffect(() => {
    const instance = chartRef.current?.getEchartsInstance();
    if (!instance) {
      return;
    }
    instance.setOption(echartsOption, false);
  }, [chartDataVersion, echartsOption, indicatorLayout]);

  if (dataSourceMode === "tickflow" && bars.length === 0) {
    return (
      <div className="flex min-h-[460px] items-center justify-center bg-slate-50 text-sm font-bold text-slate-500">
        暂无 K 线数据
      </div>
    );
  }

  return (
    <div className="tickflow-kline-chart h-full min-h-[460px] bg-white">
      <ReactKLineChart
        key={`${dataSourceMode}-${symbol}-${period}`}
        ref={chartRef}
        adjust="qfq"
        dataProvider={tickflowDataProvider}
        height={height}
        indicatorOptions={indicatorOptions}
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
      amount: bar.amount ?? null,
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

function normalizeKlineDate(value: string): string {
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}

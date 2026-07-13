"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { MarkAreaComponent } from "echarts/components";
import { use as useEcharts } from "echarts/core";
import {
  KLineChart,
  type KLineChartProps,
  type KLineChartRef,
  type KlineData,
  type KLineDataProvider,
  type ThemeConfig,
  type VisibleRange,
} from "kline-charts-react";
import {
  buildKlineIndicatorOptions,
  buildKlinePanes,
  type KlineMovingAverage,
  type KlineSubIndicator,
} from "../lib/klineIndicatorLayout";
import { buildTickFlowOverlayOption } from "../lib/brickIndicator";
import { resolveKlineOverlaySeries, resolveVisibleBarCount, type KlineSeriesSnapshot } from "../lib/chanlunOverlay.ts";
import type { ChanlunAnalysisResponse, ChanlunLayerKey, GsgfChartAnnotation, KlineBar } from "../lib/types";

useEcharts([MarkAreaComponent]);

export type KlineChartDataSourceMode = "tickflow";
export type KlineChartPeriod = NonNullable<KLineChartProps["period"]>;

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
  chanlunLayers?: Partial<Record<ChanlunLayerKey, boolean>>;
  dataSourceMode?: KlineChartDataSourceMode;
  height: number;
  movingAverages: KlineMovingAverage[];
  period: KlineChartPeriod;
  showGsgfAnnotations: boolean;
  subIndicators: KlineSubIndicator[];
  symbol: string;
}) {
  const chartRef = useRef<KLineChartRef>(null);
  const [visibleBarCount, setVisibleBarCount] = useState(120);
  const [baseSnapshot, setBaseSnapshot] = useState<KlineSeriesSnapshot | null>(null);
  const chartData = useMemo(() => convertBarsForKlineChart(bars, symbol), [bars, symbol]);
  const chartKey = useMemo(() => buildChartKey(symbol, period, chartData), [chartData, period, symbol]);
  const handleVisibleRangeChange = useCallback((range: VisibleRange) => {
    setVisibleBarCount(resolveVisibleBarCount(chartData.length, range));
  }, [chartData.length]);
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
  const chanlunOption = useMemo(
    () =>
      buildTickFlowOverlayOption({
        annotations,
        chanlun,
        chanlunLayers,
        chartData,
        showGsgfAnnotations: dataSourceMode === "tickflow" && showGsgfAnnotations,
        subIndicators,
        visibleBarCount,
      }),
    [
      annotations,
      chanlun,
      chanlunLayers,
      chartData,
      dataSourceMode,
      showGsgfAnnotations,
      subIndicators,
      visibleBarCount,
    ],
  );
  const echartsOption = useMemo(
    () => {
      const series = resolveKlineOverlaySeries(
        baseSnapshot,
        chartKey,
        Array.isArray(chanlunOption.series) ? chanlunOption.series as Record<string, unknown>[] : [],
      );
      return series ? { ...chanlunOption, series } : undefined;
    },
    [baseSnapshot, chanlunOption, chartKey],
  );
  const handleDataLoad = useCallback((_data: KlineData[]) => {
    const baseOption = chartRef.current?.getEchartsInstance()?.getOption();
    const series = Array.isArray(baseOption?.series) ? baseOption.series as Record<string, unknown>[] : [];
    if (series.length > 0) {
      setBaseSnapshot({ key: chartKey, series });
    }
  }, [chartKey]);

  if (dataSourceMode === "tickflow" && bars.length === 0) {
    return (
      <div className="flex min-h-[460px] items-center justify-center bg-slate-50 text-sm font-bold text-slate-500">
        暂无 K 线数据
      </div>
    );
  }

  return (
    <div className="tickflow-kline-chart h-full min-h-[460px] bg-white">
      <KLineChart
        key={`${dataSourceMode}-${symbol}-${period}`}
        ref={chartRef}
        adjust="qfq"
        dataProvider={tickflowDataProvider}
        echartsOption={echartsOption}
        height={height}
        indicatorOptions={indicatorOptions}
        indicators={indicatorLayout.chartIndicators}
        market="A"
        maxSubPanes={subIndicators.length}
        onDataLoad={handleDataLoad}
        onVisibleRangeChange={handleVisibleRangeChange}
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

function buildChartKey(symbol: string, period: KlineChartPeriod, bars: readonly KlineData[]): string {
  const latest = bars.at(-1);
  return [symbol, period, bars.length, latest?.date ?? "", latest?.open ?? "", latest?.close ?? "", latest?.high ?? "", latest?.low ?? ""].join("|");
}

"use client";

import type { EChartsOption, EChartsType } from "echarts";
import { useEffect, useRef } from "react";

export function OverviewTrendChart({ className = "", option }: { className?: string; option: unknown }) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    let chart: EChartsType | null = null;
    let observer: ResizeObserver | null = null;
    let cancelled = false;

    void import("echarts").then((echarts) => {
      if (cancelled || !chartRef.current) {
        return;
      }
      chart = echarts.init(chartRef.current);
      chart.setOption(option as EChartsOption, true);
      if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => chart?.resize());
        observer.observe(chartRef.current);
      }
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      chart?.dispose();
    };
  }, [option]);

  return <div className={`market-trend-chart ${className}`.trim()} ref={chartRef} />;
}

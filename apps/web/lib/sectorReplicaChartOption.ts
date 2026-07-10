import type { SectorReplicaChartSeries, SectorReplicaMode } from "./types";

const WORKBENCH_SURFACE = "#f8f7f4";
const WORKBENCH_SURFACE_MUTED = "#eee9df";
const WORKBENCH_BORDER = "#ddd8d0";
const WORKBENCH_INK = "#11100e";
const WORKBENCH_MUTED = "#7b756d";
const MARKET_RED = "#b42318";
const MARKET_GREEN = "#2f6f4a";
const MARKET_WARNING = "#8a5a10";
const MARKET_BLUE = "#2563a8";
const MARKET_PURPLE = "#6955a3";
const MARKET_CYAN = "#287f7f";
const MARKET_MAGENTA = "#9f4f78";
const MARKET_BROWN = "#806044";

export type SectorReplicaChartOptionInput = {
  axis: string[];
  compact?: boolean;
  series: SectorReplicaChartSeries[];
  mode?: SectorReplicaMode;
};

export function buildSectorReplicaChartOption({
  axis,
  compact = false,
  series,
  mode = "strength",
}: SectorReplicaChartOptionInput) {
  const compactLabelIndices = new Set<number>();
  const keyTimeIndices = axis.reduce<number[]>((indices, value, index) => {
    if (isReplicaKeyTime(value)) {
      indices.push(index);
    }
    return indices;
  }, []);
  keyTimeIndices.forEach((index, ordinal) => {
    if (ordinal % 2 === 0 || ordinal === keyTimeIndices.length - 1) {
      compactLabelIndices.add(index);
    }
  });

  return {
    animationDuration: 160,
    backgroundColor: WORKBENCH_SURFACE,
    color: [
      MARKET_RED,
      MARKET_WARNING,
      MARKET_BLUE,
      MARKET_PURPLE,
      MARKET_GREEN,
      MARKET_MAGENTA,
      WORKBENCH_MUTED,
      MARKET_BROWN,
      MARKET_CYAN,
    ],
    grid: {
      left: "2.5%",
      right: compact ? "4%" : "1%",
      bottom: "5%",
      top: "10%",
      containLabel: true,
    },
    legend: {
      top: 4,
      left: "center",
      itemGap: 18,
      itemHeight: 8,
      itemWidth: 18,
      textStyle: { color: WORKBENCH_INK, fontSize: 12 },
      data: series.map((item) => item.name),
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: "rgba(248,247,244,0.96)",
      borderColor: WORKBENCH_BORDER,
      borderWidth: 1,
      textStyle: { color: WORKBENCH_INK, fontSize: 12 },
      axisPointer: {
        type: "cross",
        lineStyle: { color: WORKBENCH_MUTED, type: "dashed", width: 1 },
      },
      valueFormatter: (value: unknown) => formatReplicaAxisValue(value, mode),
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: axis,
      axisLine: { lineStyle: { color: WORKBENCH_BORDER } },
      axisTick: { show: false },
      axisLabel: {
        color: WORKBENCH_MUTED,
        fontSize: 11,
        hideOverlap: true,
        interval: (index: number, value: string) =>
          compact ? compactLabelIndices.has(index) : isReplicaKeyTime(value),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: WORKBENCH_MUTED,
        fontSize: 11,
        formatter: (value: number) => formatReplicaAxisValue(value, mode),
      },
      splitLine: { lineStyle: { color: WORKBENCH_SURFACE_MUTED, width: 1 } },
      splitNumber: 6,
    },
    series: series.map((item, index) => ({
      name: item.name,
      type: "line",
      data: item.data,
      smooth: item.smooth ? 0.32 : false,
      showSymbol: item.showSymbol,
      connectNulls: true,
      symbol: "circle",
      symbolSize: 4,
      lineStyle: { width: index === 0 ? 2.2 : 1.7 },
      emphasis: { focus: "series" },
    })),
  };
}

function isReplicaKeyTime(value: string): boolean {
  return ["09:15", "09:25", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00"].includes(value);
}

function formatReplicaAxisValue(value: unknown, mode: SectorReplicaMode): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return String(value ?? "--");
  }
  if (mode === "main_flow") {
    return formatReplicaMoney(value);
  }
  if (Math.abs(value) >= 1000) {
    return value.toFixed(0);
  }
  return value.toFixed(1).replace(".0", "");
}

function formatReplicaMoney(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 100_000_000) {
    return `${sign}${(abs / 100_000_000).toFixed(1)}亿`;
  }
  if (abs >= 10_000) {
    return `${sign}${(abs / 10_000).toFixed(0)}万`;
  }
  return `${sign}${abs.toFixed(0)}`;
}

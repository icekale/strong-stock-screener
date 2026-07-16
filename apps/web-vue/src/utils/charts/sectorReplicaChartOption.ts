import type { SectorReplicaChartSeries, SectorReplicaMode } from "@/service/types";

const APP_RAISED = "#f7f9fc";
const APP_BORDER = "#d9e2ed";
const APP_INK = "#182336";
const APP_MUTED = "#697991";
const MARKET_RISE = "#d9363e";
const MARKET_FALL = "#07845e";
const MARKET_WARNING = "#a86000";
const MARKET_BLUE = "#1769e0";
const MARKET_PURPLE = "#7552a5";
const MARKET_CYAN = "#087a86";
const MARKET_MAGENTA = "#b23a7c";
const MARKET_GOLD = "#b88813";

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
    backgroundColor: APP_RAISED,
    color: [
      MARKET_RISE,
      MARKET_WARNING,
      MARKET_BLUE,
      MARKET_PURPLE,
      MARKET_FALL,
      MARKET_MAGENTA,
      APP_MUTED,
      MARKET_GOLD,
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
      textStyle: { color: APP_INK, fontSize: 12 },
      data: series.map((item) => item.name),
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: "rgba(247,249,252,0.96)",
      borderColor: APP_BORDER,
      borderWidth: 1,
      textStyle: { color: APP_INK, fontSize: 12 },
      axisPointer: {
        type: "cross",
        lineStyle: { color: APP_MUTED, type: "dashed", width: 1 },
      },
      valueFormatter: (value: unknown) => formatReplicaAxisValue(value, mode),
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: axis,
      axisLine: { lineStyle: { color: APP_BORDER } },
      axisTick: { show: false },
      axisLabel: {
        color: APP_MUTED,
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
        color: APP_MUTED,
        fontSize: 11,
        formatter: (value: number) => formatReplicaAxisValue(value, mode),
      },
      splitLine: { lineStyle: { color: APP_BORDER, width: 1 } },
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

export function buildSectorReplicaOption(input: SectorReplicaChartOptionInput) {
  return buildSectorReplicaChartOption(input);
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

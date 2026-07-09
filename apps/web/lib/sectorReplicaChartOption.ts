import type { SectorReplicaChartSeries, SectorReplicaMode } from "./types";

export type SectorReplicaChartOptionInput = {
  axis: string[];
  series: SectorReplicaChartSeries[];
  mode?: SectorReplicaMode;
};

export function buildSectorReplicaChartOption({ axis, series, mode = "strength" }: SectorReplicaChartOptionInput) {
  return {
    animationDuration: 160,
    backgroundColor: "#ffffff",
    color: ["#d62f2f", "#f08a24", "#2f67c7", "#7b61d8", "#11a37f", "#d14f9f", "#7c8798", "#a35d23"],
    grid: { left: "2.5%", right: "1%", bottom: "5%", top: "10%", containLabel: true },
    legend: {
      top: 4,
      left: "center",
      itemGap: 18,
      itemHeight: 8,
      itemWidth: 18,
      textStyle: { color: "#333333", fontSize: 12 },
      data: series.map((item) => item.name),
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "#d8d8d8",
      borderWidth: 1,
      textStyle: { color: "#222222", fontSize: 12 },
      axisPointer: {
        type: "cross",
        lineStyle: { color: "#8d8d8d", type: "dashed", width: 1 },
      },
      valueFormatter: (value: unknown) => formatReplicaAxisValue(value, mode),
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: axis,
      axisLine: { lineStyle: { color: "#9d9d9d" } },
      axisTick: { show: false },
      axisLabel: {
        color: "#555555",
        fontSize: 11,
        hideOverlap: true,
        interval: (_index: number, value: string) => isReplicaKeyTime(value),
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#555555",
        fontSize: 11,
        formatter: (value: number) => formatReplicaAxisValue(value, mode),
      },
      splitLine: { lineStyle: { color: "#ececec", width: 1 } },
      splitNumber: 6,
    },
    series: series.map((item, index) => ({
      name: item.name,
      type: "line",
      data: item.data,
      smooth: item.smooth ? 0.15 : false,
      showSymbol: item.showSymbol,
      connectNulls: true,
      symbol: "circle",
      symbolSize: 4,
      lineStyle: { width: index === 0 ? 1.9 : 1.55 },
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

import type { EChartsOption } from "echarts";
import type { MarketEmotionSample, MarketEmotionSnapshotResponse } from "./types";

const APP_BORDER = "#d9e2ed";
const APP_INK = "#182336";
const APP_MUTED = "#697991";
const APP_PRIMARY = "#1769e0";
const MARKET_RISE = "#d9363e";

export type MarketEmotionTrend = {
  breadth: Array<number | null>;
  emotion: number[];
  latest: {
    emotionLevel: string;
    emotionScore: number;
    limitDownCount: number | null;
    limitUpCount: number;
  };
  scoreChange: number | null;
  times: string[];
};

export function buildMarketEmotionTrend(data: MarketEmotionSnapshotResponse): MarketEmotionTrend {
  const deduped = new Map<string, MarketEmotionSample>();
  for (const sample of data.samples) {
    deduped.set(sample.sampled_at, sample);
  }
  const samples = Array.from(deduped.values())
    .filter((sample) => isIntradaySample(sample.sampled_at))
    .sort((left, right) => Date.parse(left.sampled_at) - Date.parse(right.sampled_at));
  const latestSample = samples.at(-1);
  const firstSample = samples[0];

  return {
    breadth: samples.map((sample) => marketBreadthPercent(sample.advance_count, sample.decline_count)),
    emotion: samples.map((sample) => sample.emotion_score),
    latest: {
      emotionLevel: data.metrics.emotion_level,
      emotionScore: data.metrics.emotion_score,
      limitDownCount: data.metrics.limit_down_count,
      limitUpCount: data.metrics.limit_up_count,
    },
    scoreChange:
      samples.length >= 2 && firstSample && latestSample
        ? roundToTwo(latestSample.emotion_score - firstSample.emotion_score)
        : null,
    times: samples.map((sample) => formatSampleTime(sample.sampled_at)),
  };
}

export function buildMarketEmotionChartOption(trend: MarketEmotionTrend): EChartsOption {
  const lastIndex = trend.times.length - 1;
  const series = [
    { name: "情绪分", data: trend.emotion, color: APP_PRIMARY },
    { name: "上涨占比", data: trend.breadth, color: MARKET_RISE },
  ];

  return {
    animationDuration: 160,
    backgroundColor: "transparent",
    color: series.map((item) => item.color),
    grid: { bottom: 8, containLabel: true, left: 4, right: 12, top: 34 },
    legend: {
      data: series.map((item) => item.name),
      itemGap: 16,
      itemHeight: 7,
      itemWidth: 16,
      left: 0,
      textStyle: { color: APP_INK, fontSize: 11 },
      top: 2,
    },
    series: series.map((item) => ({
      data: item.data,
      emphasis: { focus: "series" },
      lineStyle: { color: item.color, width: 2 },
      name: item.name,
      showSymbol: true,
      smooth: 0.24,
      symbol: "circle",
      symbolSize: (_value: unknown, params: { dataIndex: number }) => (params.dataIndex === lastIndex ? 5 : 0),
      type: "line",
    })),
    tooltip: {
      axisPointer: { lineStyle: { color: APP_MUTED, type: "dashed", width: 1 }, type: "line" },
      backgroundColor: "rgba(247,249,252,0.98)",
      borderColor: APP_BORDER,
      borderWidth: 1,
      confine: true,
      textStyle: { color: APP_INK, fontSize: 12 },
      trigger: "axis",
    },
    xAxis: {
      axisLabel: { color: APP_MUTED, fontSize: 10, hideOverlap: true },
      axisLine: { lineStyle: { color: APP_BORDER } },
      axisTick: { show: false },
      boundaryGap: false,
      data: trend.times,
      type: "category",
    },
    yAxis: {
      axisLabel: { color: APP_MUTED, fontSize: 10, formatter: "{value}" },
      axisLine: { show: false },
      axisTick: { show: false },
      max: 100,
      min: 0,
      splitLine: { lineStyle: { color: APP_BORDER, width: 1 } },
      splitNumber: 4,
      type: "value",
    },
  };
}

function marketBreadthPercent(advanceCount: number | null, declineCount: number | null): number | null {
  if (advanceCount === null || declineCount === null) {
    return null;
  }
  const total = advanceCount + declineCount;
  return total > 0 ? roundToTwo((advanceCount / total) * 100) : null;
}

function formatSampleTime(value: string): string {
  return value.match(/(?:T|\s)(\d{2}:\d{2})/)?.[1] ?? value;
}

function isIntradaySample(value: string): boolean {
  const time = formatSampleTime(value);
  const [hour, minute] = time.split(":").map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return false;
  }
  const minutes = hour * 60 + minute;
  return (
    (minutes >= 9 * 60 + 15 && minutes <= 11 * 60 + 30) ||
    (minutes >= 13 * 60 && minutes <= 15 * 60)
  );
}

function roundToTwo(value: number): number {
  return Math.round(value * 100) / 100;
}

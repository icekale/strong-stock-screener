import assert from "node:assert/strict";
import test from "node:test";
import type { MarketEmotionSample, MarketEmotionSnapshotResponse } from "./types";
const { buildMarketEmotionChartOption, buildMarketEmotionTrend } = (await import(
  new URL("./marketOverviewTrend.ts", import.meta.url).href
)) as typeof import("./marketOverviewTrend");

test("market emotion trend sorts samples and calculates breadth", () => {
  const trend = buildMarketEmotionTrend(snapshot([
    sample("2026-07-10T10:00:00+08:00", 52, 3000, 2000),
    sample("2026-07-10T09:30:00+08:00", 41, 2000, 3000),
  ]));

  assert.deepEqual(trend.times, ["09:30", "10:00"]);
  assert.deepEqual(trend.emotion, [41, 52]);
  assert.deepEqual(trend.breadth, [40, 60]);
  assert.equal(trend.scoreChange, 11);
  assert.deepEqual(trend.latest, {
    emotionLevel: "良好",
    emotionScore: 52,
    limitDownCount: 4,
    limitUpCount: 80,
  });
});

test("market emotion trend keeps the last duplicate timestamp and preserves missing breadth", () => {
  const duplicate = sample("2026-07-10T10:00:00+08:00", 58, null, null);
  const trend = buildMarketEmotionTrend(snapshot([
    sample("2026-07-10T10:00:00+08:00", 50, 3000, 2000),
    duplicate,
  ]));

  assert.deepEqual(trend.times, ["10:00"]);
  assert.deepEqual(trend.emotion, [58]);
  assert.deepEqual(trend.breadth, [null]);
  assert.equal(trend.scoreChange, null);
});

test("market emotion trend keeps current summary when history is empty", () => {
  const data = snapshot([]);
  data.metrics.emotion_score = 63.5;
  data.metrics.emotion_level = "良好";
  data.metrics.limit_up_count = 91;
  data.metrics.limit_down_count = 3;

  const trend = buildMarketEmotionTrend(data);

  assert.deepEqual(trend.times, []);
  assert.deepEqual(trend.emotion, []);
  assert.deepEqual(trend.breadth, []);
  assert.equal(trend.scoreChange, null);
  assert.equal(trend.latest.emotionScore, 63.5);
  assert.equal(trend.latest.limitUpCount, 91);
});

test("market emotion trend excludes lunch and after-hours samples", () => {
  const data = snapshot([
    sample("2026-07-10T10:00:00+08:00", 45, 2400, 2600),
    sample("2026-07-10T12:00:00+08:00", 48, 2500, 2500),
    sample("2026-07-10T14:30:00+08:00", 55, 3200, 1800),
    sample("2026-07-10T22:00:00+08:00", 68, 4000, 1000),
  ]);
  data.metrics.emotion_score = 68;
  data.metrics.emotion_level = "良好";

  const trend = buildMarketEmotionTrend(data);

  assert.deepEqual(trend.times, ["10:00", "14:30"]);
  assert.deepEqual(trend.emotion, [45, 55]);
  assert.equal(trend.scoreChange, 10);
  assert.equal(trend.latest.emotionScore, 68);
});

test("market emotion chart uses a shared zero to one hundred scale without area decoration", () => {
  const option = buildMarketEmotionChartOption(buildMarketEmotionTrend(snapshot([
    sample("2026-07-10T09:30:00+08:00", 41, 2000, 3000),
    sample("2026-07-10T10:00:00+08:00", 52, 3000, 2000),
  ]))) as {
    backgroundColor: string;
    series: Array<{ areaStyle?: unknown; data: Array<number | null>; name: string }>;
    xAxis: { data: string[] };
    yAxis: { max: number; min: number };
  };

  assert.equal(option.backgroundColor, "transparent");
  assert.deepEqual(option.xAxis.data, ["09:30", "10:00"]);
  assert.equal(option.yAxis.min, 0);
  assert.equal(option.yAxis.max, 100);
  assert.deepEqual(option.series.map((item) => item.name), ["情绪分", "上涨占比"]);
  assert.ok(option.series.every((item) => item.areaStyle === undefined));
});

function sample(
  sampledAt: string,
  emotionScore: number,
  advanceCount: number | null,
  declineCount: number | null,
): MarketEmotionSample {
  return {
    advance_count: advanceCount,
    break_board_count: 10,
    decline_count: declineCount,
    emotion_level: emotionScore >= 50 ? "良好" : "一般",
    emotion_score: emotionScore,
    limit_down_count: 4,
    limit_up_count: 80,
    losing_effect_score: 20,
    max_consecutive_boards: 3,
    sampled_at: sampledAt,
    seal_rate_pct: 70,
    trade_date: "2026-07-10",
    turnover_change_pct: 5,
    turnover_cny: 1_000_000,
  };
}

function snapshot(samples: MarketEmotionSample[]): MarketEmotionSnapshotResponse {
  const latest = samples.toSorted((left, right) => Date.parse(left.sampled_at) - Date.parse(right.sampled_at)).at(-1);
  return {
    buckets: [],
    generated_at: "2026-07-10T10:00:00+08:00",
    metrics: {
      advance_count: latest?.advance_count ?? null,
      break_board_count: latest?.break_board_count ?? 10,
      decline_count: latest?.decline_count ?? null,
      emotion_level: latest?.emotion_level ?? "一般",
      emotion_score: latest?.emotion_score ?? 35,
      limit_down_count: latest?.limit_down_count ?? 4,
      limit_up_count: latest?.limit_up_count ?? 80,
      losing_effect_score: latest?.losing_effect_score ?? 20,
      main_flow_cny: null,
      max_consecutive_boards: latest?.max_consecutive_boards ?? 3,
      seal_rate_pct: latest?.seal_rate_pct ?? 70,
      turnover_change_cny: null,
      turnover_change_pct: latest?.turnover_change_pct ?? 5,
      turnover_cny: latest?.turnover_cny ?? 1_000_000,
      yesterday_ladder_performance_pct: null,
      yesterday_limit_up_performance_pct: null,
    },
    notes: [],
    samples,
    source_status: [],
    trade_date: "2026-07-10",
  };
}

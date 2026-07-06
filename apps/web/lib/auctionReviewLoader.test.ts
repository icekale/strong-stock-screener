import assert from "node:assert/strict";
import test from "node:test";

import type { AuctionReviewRecord, AuctionReviewSummary, AuctionRuleBucket } from "./types";

const {
  loadAuctionReviewSummaryForDate,
} = (await import(new URL("./auctionReviewLoader.ts", import.meta.url).href)) as typeof import("./auctionReviewLoader");

function summary(
  tradeDate: string | null,
  records: AuctionReviewRecord[] = [],
  buckets: AuctionRuleBucket[] = [],
): AuctionReviewSummary {
  return {
    buckets,
    completed_count: 0,
    data_incomplete_count: 0,
    generated_at: "2026-07-06T16:00:00+08:00",
    pending_count: records.length,
    record_count: records.length,
    records,
    source_status: [],
    trade_date: tradeDate,
  };
}

function record(symbol: string, tradeDate: string, closePct: number | null): AuctionReviewRecord {
  return {
    auction_snapshot: {
      auction_score: 80,
      current_pct_change: 4.6,
      open_gap_pct: 3.8,
      quote_time: null,
      rank: 1,
      risk_flags: [],
      signals: [],
      tier: "strong_high_open",
      turnover_cny: 360_000_000,
      turnover_rate: 6.2,
      volume: null,
    },
    day_result: {
      close_pct: closePct,
      drawdown_pct: null,
      limit_up: null,
      open_pct: null,
      peak_pct: null,
      status: closePct === null ? "pending" : "complete",
      strong_follow: null,
    },
    industry: "半导体",
    intraday_result: {
      close_pct: null,
      drawdown_pct: null,
      limit_up: null,
      open_pct: null,
      peak_pct: null,
      status: "pending",
      strong_follow: null,
    },
    name: symbol,
    next_day_result: {
      close_pct: null,
      drawdown_pct: null,
      limit_up: null,
      open_pct: null,
      peak_pct: null,
      status: "pending",
      strong_follow: null,
    },
    review_status: closePct === null ? "pending" : "day_done",
    rule_tags: [],
    score: {
      day_score: null,
      intraday_score: null,
      next_day_score: null,
      total_score: null,
    },
    selected_at: `${tradeDate}T09:25:00+08:00`,
    selected_at_label: "09:25",
    source_status: [],
    symbol,
    trade_date: tradeDate,
  };
}

test("auction review loader prefers current trade date records over stale latest summary", async () => {
  const current = summary("2026-07-06", [record("301308.SZ", "2026-07-06", 4.56)]);
  const staleLatest = summary("2026-07-02", [record("600641.SH", "2026-07-02", -1.23)]);
  const rules = summary(null, [], [
    {
      avg_close_pct: 1.2,
      avg_drawdown_pct: -2.1,
      avg_intraday_peak_pct: 3.4,
      avg_next_open_pct: null,
      avg_score: 65,
      failure_count: 1,
      rule_tag: "强势高开",
      sample_count: 8,
      suggestion: "保留观察",
      win_rate: 0.625,
    },
  ]);

  const result = await loadAuctionReviewSummaryForDate("2026-07-06", {
    getAuctionReview: async (tradeDate, limit) => {
      assert.equal(tradeDate, "2026-07-06");
      assert.equal(limit, 500);
      return current;
    },
    getAuctionReviewLatest: async () => staleLatest,
    getAuctionRuleSummary: async (limit) => {
      assert.equal(limit, 2000);
      return rules;
    },
  });

  assert.equal(result?.trade_date, "2026-07-06");
  assert.deepEqual(
    result?.records.map((item) => item.symbol),
    ["301308.SZ"],
  );
  assert.deepEqual(
    result?.buckets.map((bucket) => bucket.rule_tag),
    ["强势高开"],
  );
});

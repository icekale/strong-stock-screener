import assert from "node:assert/strict";
import test from "node:test";

import type { AuctionReviewRecord } from "./types";

const {
  buildAuctionClosePctBySymbol,
} = (await import(new URL("./auctionReviewMetrics.ts", import.meta.url).href)) as typeof import("./auctionReviewMetrics");

function reviewRecord(
  symbol: string,
  tradeDate: string,
  closePct: number | null,
): AuctionReviewRecord {
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
      status: closePct === null ? "pending" : "done",
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
    review_status: "day_done",
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

test("auction close pct map uses same-day review records only", () => {
  const closePctBySymbol = buildAuctionClosePctBySymbol(
    [
      reviewRecord("300001.SZ", "2026-07-06", 2.34),
      reviewRecord("300002.SZ", "2026-07-05", -1.23),
    ],
    "2026-07-06",
  );

  assert.equal(closePctBySymbol.get("300001.SZ"), 2.34);
  assert.equal(closePctBySymbol.has("300002.SZ"), false);
});

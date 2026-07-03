import assert from "node:assert/strict";
import test from "node:test";

import type { AuctionSnapshotItem } from "./types";

const {
  AUCTION_LOW_TURNOVER_CNY,
  getAuctionLiquidityWarning,
  sortAuctionItems,
} = (await import(new URL("./auctionSort.ts", import.meta.url).href)) as typeof import("./auctionSort");

function item(
  symbol: string,
  overrides: Partial<AuctionSnapshotItem> = {},
): AuctionSnapshotItem {
  return {
    action_note: null,
    auction_score: 50,
    current_pct_change: 0,
    industry: "未标注",
    last_price: null,
    name: symbol,
    open_gap_pct: 0,
    quote_time: null,
    risk_flags: [],
    signals: [],
    symbol,
    themes: [],
    hot_theme_rank: null,
    hot_theme_score: null,
    theme_auction_rank: null,
    theme_resonance: false,
    tier: "neutral",
    turnover_cny: 0,
    turnover_rate: 0,
    volume: null,
    ...overrides,
  };
}

test("auction综合强度排序优先保留模型分，不被成交额单独覆盖", () => {
  const sorted = sortAuctionItems([
    item("低分大额", { auction_score: 50, turnover_cny: 900_000_000 }),
    item("高分中额", { auction_score: 80, turnover_cny: 120_000_000 }),
  ], "score");

  assert.deepEqual(sorted.map((entry) => entry.symbol), ["高分中额", "低分大额"]);
});

test("auction成交额优先排序把流动性最大的候选放在前面", () => {
  const sorted = sortAuctionItems([
    item("高分中额", { auction_score: 80, turnover_cny: 120_000_000 }),
    item("低分大额", { auction_score: 50, turnover_cny: 900_000_000 }),
  ], "turnover");

  assert.deepEqual(sorted.map((entry) => entry.symbol), ["低分大额", "高分中额"]);
});

test("auction行业聚集排序优先显示同一行业候选更多的方向", () => {
  const sorted = sortAuctionItems([
    item("贵金属一", { auction_score: 78, industry: "贵金属", turnover_cny: 200_000_000 }),
    item("半导体一", { auction_score: 70, industry: "半导体", turnover_cny: 100_000_000 }),
    item("半导体二", { auction_score: 68, industry: "半导体", turnover_cny: 90_000_000 }),
  ], "industry");

  assert.deepEqual(sorted.map((entry) => entry.symbol), ["半导体一", "半导体二", "贵金属一"]);
});

test("auction低成交额候选给出流动性风险提示", () => {
  assert.equal(AUCTION_LOW_TURNOVER_CNY, 30_000_000);
  assert.equal(getAuctionLiquidityWarning(item("低额", { turnover_cny: 18_000_000 })), "成交额不足");
  assert.equal(getAuctionLiquidityWarning(item("足额", { turnover_cny: 80_000_000 })), null);
});

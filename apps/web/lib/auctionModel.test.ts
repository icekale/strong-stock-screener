import assert from "node:assert/strict";
import test from "node:test";

import type { AuctionModelPredictionItem } from "./types";

const {
  AUCTION_MODEL_PREVIEW_LIMIT,
  auctionModelBucketLabel,
  auctionModelCacheStatusLabel,
  auctionModelLiveConfirmationColor,
  auctionModelLiveConfirmationLabel,
  auctionModelRunStatusText,
  selectAuctionModelPreviewItems,
} = (await import(new URL("./auctionModel.ts", import.meta.url).href)) as typeof import("./auctionModel");

function item(symbol: string, overrides: Partial<AuctionModelPredictionItem> = {}): AuctionModelPredictionItem {
  return {
    bucket: "watch",
    data_quality: [],
    feature_end_date: "2026-07-03",
    guard_rule: null,
    name: symbol,
    prev_close_price: null,
    prob_3pct: 0.5,
    rank: null,
    market_cap_float: null,
    avg_amount_3d: null,
    risk_flags: [],
    strategy_note: null,
    symbol,
    trend_reasons: [],
    ...overrides,
  };
}

test("auction model preview keeps selected top3 before lower buckets", () => {
  const preview = selectAuctionModelPreviewItems([
    item("观察", { bucket: "watch", rank: 4, prob_3pct: 0.8 }),
    item("入选二", { bucket: "selected", rank: 2, prob_3pct: 0.86 }),
    item("攻击", { bucket: "attack", rank: 3, prob_3pct: 0.83 }),
    item("入选一", { bucket: "selected", rank: 1, prob_3pct: 0.91 }),
  ]);

  assert.equal(AUCTION_MODEL_PREVIEW_LIMIT, 3);
  assert.deepEqual(preview.map((entry) => entry.symbol), ["入选一", "入选二", "攻击"]);
});

test("auction model bucket labels are trading-workbench copy", () => {
  assert.equal(auctionModelBucketLabel("selected"), "Top3试运行");
  assert.equal(auctionModelBucketLabel("attack"), "攻击观察");
  assert.equal(auctionModelBucketLabel("watch"), "候选观察");
  assert.equal(auctionModelBucketLabel("avoid"), "回避");
});

test("auction model cache status labels separate cached and regenerated runs", () => {
  assert.equal(auctionModelCacheStatusLabel("cached"), "缓存结果");
  assert.equal(auctionModelCacheStatusLabel("generated"), "刚生成");
});

test("auction model live confirmation labels and colors are compact", () => {
  assert.equal(auctionModelLiveConfirmationLabel("buyable"), "可买");
  assert.equal(auctionModelLiveConfirmationLabel("watch"), "观察");
  assert.equal(auctionModelLiveConfirmationLabel("reject"), "放弃");
  assert.equal(auctionModelLiveConfirmationColor("buyable"), "red");
  assert.equal(auctionModelLiveConfirmationColor("watch"), "orange");
  assert.equal(auctionModelLiveConfirmationColor("reject"), "default");
});

test("auction model status text stays compact before and after a run", () => {
  assert.equal(auctionModelRunStatusText(null), "未运行 · 运行后显示Top3候选");
  assert.equal(
    auctionModelRunStatusText({
      feature_end_date: "2026-07-03",
      items: [
        item("入选一", { bucket: "selected", rank: 1 }),
        item("入选二", { bucket: "selected", rank: 2 }),
        item("观察", { bucket: "watch", rank: 3 }),
      ],
    }),
    "已生成 · 预览3只 · 特征日 2026-07-03",
  );
});

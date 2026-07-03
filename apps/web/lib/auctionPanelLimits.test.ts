import assert from "node:assert/strict";
import test from "node:test";

const {
  AUCTION_MAINLINE_TOP_LIMIT,
  AUCTION_RISK_FOCUS_LIMIT,
  selectAuctionMainlineTopItems,
  selectAuctionRiskFocusItems,
} = (await import(new URL("./auctionPanelLimits.ts", import.meta.url).href)) as typeof import("./auctionPanelLimits");

test("auction side panels keep five mainline industries and five risk focus stocks visible", () => {
  const items = Array.from({ length: 7 }, (_, index) => ({ id: index + 1 }));

  assert.equal(AUCTION_MAINLINE_TOP_LIMIT, 5);
  assert.equal(AUCTION_RISK_FOCUS_LIMIT, 5);
  assert.deepEqual(
    selectAuctionMainlineTopItems(items).map((item) => item.id),
    [1, 2, 3, 4, 5],
  );
  assert.deepEqual(
    selectAuctionRiskFocusItems(items).map((item) => item.id),
    [1, 2, 3, 4, 5],
  );
});

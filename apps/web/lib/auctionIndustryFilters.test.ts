import assert from "node:assert/strict";
import test from "node:test";

const {
  AUCTION_HOT_INDUSTRY_LIMIT,
  selectAuctionFocusIndustryItems,
  selectAuctionHotIndustryItems,
} = (await import(new URL("./auctionIndustryFilters.ts", import.meta.url).href)) as typeof import("./auctionIndustryFilters");

type Stat = {
  count: number;
  industry: string;
};

const stats: Stat[] = [
  "汽车零部件",
  "通用设备",
  "自动化设备",
  "贵金属",
  "电网设备",
  "未标注",
  "军工装备",
  "消费电子",
  "塑料制品",
  "通信设备",
  "半导体",
  "机器人",
].map((industry, index) => ({ count: 20 - index, industry }));

test("auction hot industry filter keeps the top ten visible", () => {
  assert.equal(AUCTION_HOT_INDUSTRY_LIMIT, 10);
  assert.deepEqual(
    selectAuctionHotIndustryItems(stats).map((item) => item.industry),
    [
      "汽车零部件",
      "通用设备",
      "自动化设备",
      "贵金属",
      "电网设备",
      "未标注",
      "军工装备",
      "消费电子",
      "塑料制品",
      "通信设备",
    ],
  );
});

test("auction focus industry filter keeps watched industries outside the hot list", () => {
  const hotItems = selectAuctionHotIndustryItems(stats);

  assert.deepEqual(
    selectAuctionFocusIndustryItems(stats, hotItems).map((item) => item.industry),
    ["半导体", "机器人"],
  );
});

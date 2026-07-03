export const AUCTION_HOT_INDUSTRY_LIMIT = 10;

export const AUCTION_FOCUS_INDUSTRIES = ["半导体", "消费电子", "机器人", "存储芯片"] as const;

export type AuctionIndustryItem = {
  industry: string;
};

export function selectAuctionHotIndustryItems<T>(items: readonly T[]): T[] {
  return items.slice(0, AUCTION_HOT_INDUSTRY_LIMIT);
}

export function selectAuctionFocusIndustryItems<T extends AuctionIndustryItem>(
  items: readonly T[],
  hotItems: readonly T[] = selectAuctionHotIndustryItems(items),
): T[] {
  const hotIndustries = new Set(hotItems.map((item) => item.industry));
  return AUCTION_FOCUS_INDUSTRIES.flatMap((industry) => {
    if (hotIndustries.has(industry)) {
      return [];
    }
    const item = items.find((candidate) => candidate.industry === industry);
    return item ? [item] : [];
  });
}

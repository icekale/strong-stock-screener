export const AUCTION_MAINLINE_TOP_LIMIT = 5;
export const AUCTION_RISK_FOCUS_LIMIT = 5;

export function selectAuctionMainlineTopItems<T>(items: readonly T[]): T[] {
  return items.slice(0, AUCTION_MAINLINE_TOP_LIMIT);
}

export function selectAuctionRiskFocusItems<T>(items: readonly T[]): T[] {
  return items.slice(0, AUCTION_RISK_FOCUS_LIMIT);
}

import type { AuctionReviewRecord } from "./types";

export function buildAuctionClosePctBySymbol(
  records: readonly AuctionReviewRecord[],
  tradeDate: string | null | undefined,
): Map<string, number | null> {
  if (!tradeDate) {
    return new Map();
  }
  return new Map(
    records
      .filter((record) => record.trade_date === tradeDate)
      .map((record) => [record.symbol, record.day_result.close_pct]),
  );
}

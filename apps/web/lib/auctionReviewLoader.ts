import type { AuctionReviewSummary } from "./types";

type AuctionReviewLoaders = {
  getAuctionReview: (tradeDate: string, limit?: number) => Promise<AuctionReviewSummary>;
  getAuctionReviewLatest: () => Promise<AuctionReviewSummary>;
  getAuctionRuleSummary: (limit?: number) => Promise<AuctionReviewSummary>;
};

export async function loadAuctionReviewSummaryForDate(
  tradeDate: string | null | undefined,
  loaders: AuctionReviewLoaders,
): Promise<AuctionReviewSummary | null> {
  if (tradeDate) {
    const [currentResult, latestResult, rulesResult] = await Promise.allSettled([
      loaders.getAuctionReview(tradeDate, 500),
      loaders.getAuctionReviewLatest(),
      loaders.getAuctionRuleSummary(2000),
    ]);
    return mergeAuctionReviewSummaries(
      fulfilledValue(currentResult),
      fulfilledValue(latestResult),
      fulfilledValue(rulesResult),
    );
  }

  const [latestResult, rulesResult] = await Promise.allSettled([
    loaders.getAuctionReviewLatest(),
    loaders.getAuctionRuleSummary(2000),
  ]);
  return mergeAuctionReviewSummaries(null, fulfilledValue(latestResult), fulfilledValue(rulesResult));
}

export function mergeAuctionReviewSummaries(
  current: AuctionReviewSummary | null,
  latest: AuctionReviewSummary | null,
  rules: AuctionReviewSummary | null,
): AuctionReviewSummary | null {
  const base = current ?? latest ?? rules;
  if (!base) {
    return null;
  }
  return {
    ...base,
    buckets: rules?.buckets.length ? rules.buckets : base.buckets,
  };
}

function fulfilledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

export const MARKET_VIEWS = ["sectors", "heatmap"] as const;

export type MarketView = (typeof MARKET_VIEWS)[number];

export function normalizeMarketView(value: unknown): MarketView {
  return value === "heatmap" ? "heatmap" : "sectors";
}

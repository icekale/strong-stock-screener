export type StockDetailFrom = "auction" | "auction-model" | "home" | "sectors";

export type StockDetailLinkContext = {
  from?: StockDetailFrom;
  industry?: string | null;
  name?: string | null;
};

export type StockDetailContext = {
  from: StockDetailFrom;
  industry: string | null;
  name: string | null;
  returnHref: string;
  returnLabel: string;
};

type ReadableSearchParams = {
  get: (name: string) => string | null;
};

export function buildStockDetailHref(symbol: string, context: StockDetailLinkContext = {}): string {
  const query = new URLSearchParams();
  if (context.from === "auction" || context.from === "auction-model" || context.from === "sectors") {
    query.set("from", context.from);
  }
  const name = cleanText(context.name);
  const industry = cleanText(context.industry);
  if (name) {
    query.set("name", name);
  }
  if (industry) {
    query.set("industry", industry);
  }
  const suffix = query.toString();
  return `/stock/${encodeURIComponent(symbol)}${suffix ? `?${suffix}` : ""}`;
}

export function resolveStockDetailContext(params: ReadableSearchParams): StockDetailContext {
  const source = params.get("from");
  const from: StockDetailFrom =
    source === "auction" || source === "auction-model" || source === "sectors" ? source : "home";
  return {
    from,
    industry: cleanText(params.get("industry")),
    name: cleanText(params.get("name")),
    returnHref: from === "auction" || from === "auction-model" ? "/auction" : from === "sectors" ? "/sectors" : "/",
    returnLabel:
      from === "auction"
        ? "返回竞价雷达"
        : from === "auction-model"
          ? "返回竞价模型"
          : from === "sectors"
            ? "返回题材工作台"
            : "返回选股工作台",
  };
}

function cleanText(value: string | null | undefined): string | null {
  const text = value?.trim();
  return text ? text : null;
}

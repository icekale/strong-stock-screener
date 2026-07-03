export type StockIdentity = {
  industry?: string | null;
  name?: string | null;
};

export function mergeStockIdentity(...sources: StockIdentity[]): { industry: string | null; name: string | null } {
  return {
    industry: firstText(sources.map((source) => source.industry)),
    name: firstText(sources.map((source) => source.name)),
  };
}

function firstText(values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const text = value?.trim();
    if (text) {
      return text;
    }
  }
  return null;
}

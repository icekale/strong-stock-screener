export type StockListStatus = "all" | "data_incomplete" | "focus" | "reduce_risk" | "wait_pullback";

export type FilterableStockListItem = {
  industry: string | null;
  name: string | null;
  status: Exclude<StockListStatus, "all"> | null;
  symbol: string;
};

export const stockListStatusOptions: Array<{ label: string; value: StockListStatus }> = [
  { label: "全部", value: "all" },
  { label: "重点", value: "focus" },
  { label: "等回踩", value: "wait_pullback" },
  { label: "减仓", value: "reduce_risk" },
  { label: "缺数据", value: "data_incomplete" },
];

const CHINESE_INITIALS: Record<string, string> = {
  爱: "a",
  宝: "b",
  材: "c",
  超: "c",
  电: "d",
  份: "f",
  股: "g",
  技: "j",
  科: "k",
  普: "p",
  声: "s",
  子: "z",
  中: "z",
};

export function filterStockList<T extends FilterableStockListItem>(
  items: readonly T[],
  keyword: string,
  status: StockListStatus,
): T[] {
  const normalizedKeyword = normalizeSearchText(keyword);
  return items.filter((item) => {
    if (status !== "all" && item.status !== status) {
      return false;
    }
    if (!normalizedKeyword) {
      return true;
    }
    return searchableText(item).includes(normalizedKeyword);
  });
}

export function getChineseInitials(value: string): string {
  return Array.from(value)
    .map((char) => CHINESE_INITIALS[char] ?? (/^[a-zA-Z0-9]$/.test(char) ? char.toLowerCase() : ""))
    .join("");
}

function searchableText(item: FilterableStockListItem): string {
  const name = item.name ?? "";
  return [item.symbol, item.symbol.replace(/\D/g, ""), name, getChineseInitials(name), item.industry ?? ""]
    .map(normalizeSearchText)
    .join(" ");
}

function normalizeSearchText(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "");
}

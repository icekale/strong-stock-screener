export type StockListStatus = "all" | "data_incomplete" | "focus" | "reduce_risk" | "wait_pullback";
export type GsgfSignalFilter = "all" | "b_zone_a_point" | "confirmed_buy" | "low_absorb" | "volume_breakout";

export type FilterableStockListItem = {
  gsgf?: {
    confirm_type?: string | null;
    final_status?: string | null;
    risk_flags?: readonly string[];
    setup_type?: string | null;
  } | null;
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

export const gsgfSignalFilterOptions: Array<{ label: string; value: GsgfSignalFilter }> = [
  { label: "全部", value: "all" },
  { label: "确认买点", value: "confirmed_buy" },
  { label: "低吸观察", value: "low_absorb" },
  { label: "放量突破", value: "volume_breakout" },
  { label: "B区A点", value: "b_zone_a_point" },
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

export function filterStockListByGsgf<T extends FilterableStockListItem>(
  items: readonly T[],
  signalFilter: GsgfSignalFilter,
  excludeGlobalDistributionRisk: boolean,
): T[] {
  return items.filter((item) => {
    if (excludeGlobalDistributionRisk && item.gsgf?.risk_flags?.includes("全局阴量压制")) {
      return false;
    }
    if (signalFilter === "all") {
      return true;
    }
    if (signalFilter === "confirmed_buy") {
      return item.gsgf?.final_status === "确认买点";
    }
    if (signalFilter === "low_absorb") {
      return item.gsgf?.final_status === "低吸观察";
    }
    if (signalFilter === "volume_breakout") {
      return item.gsgf?.confirm_type === "放量突破确认";
    }
    return item.gsgf?.setup_type === "B区A点";
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

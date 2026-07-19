export type NavigationGroupKey = "market" | "observe" | "system";

export type NavigationItemKey =
  | "overview"
  | "screener"
  | "auction"
  | "market"
  | "watchlist"
  | "sentiment"
  | "chanlun"
  | "system";

export type NavigationItem = {
  readonly href: string;
  readonly key: NavigationItemKey;
  readonly label: string;
};

export type NavigationGroup = {
  readonly items: readonly NavigationItem[];
  readonly key: NavigationGroupKey;
  readonly label: string;
};

export type NavigationSelection = {
  groupKey: NavigationGroupKey;
  itemKey: NavigationItemKey | null;
};

export const navigationGroups = [
  {
    key: "market",
    label: "市场",
    items: [
      { key: "overview", href: "/", label: "市场总览" },
      { key: "screener", href: "/screener", label: "强势选股" },
      { key: "auction", href: "/auction", label: "竞价雷达" },
      { key: "market", href: "/market", label: "板块与热图" },
    ],
  },
  {
    key: "observe",
    label: "观察",
    items: [
      { key: "watchlist", href: "/watchlist", label: "自选与风险" },
      { key: "sentiment", href: "/sentiment", label: "情绪与复盘" },
      { key: "chanlun", href: "/chanlun", label: "缠论工作台" },
    ],
  },
  {
    key: "system",
    label: "系统",
    items: [{ key: "system", href: "/system", label: "模型与数据源" }],
  },
] as const satisfies readonly NavigationGroup[];

const legacyDestinations: Record<string, string> = {
  "/sectors": "/market?view=sectors",
  "/heatmap": "/market?view=heatmap",
  "/model-maintenance": "/system?tab=model",
  "/settings": "/system?tab=data",
};

export function getLegacyDestination(pathname: string): string | null {
  return legacyDestinations[pathname] ?? null;
}

export function getNavigationSelection(pathname: string): NavigationSelection {
  if (pathname.startsWith("/stock/") || pathname === "/etf-radar") {
    return { groupKey: "market", itemKey: null };
  }

  const matchingItems = navigationGroups.flatMap((group) =>
    group.items
      .filter((item) => item.href === "/" || pathname === item.href || pathname.startsWith(`${item.href}/`))
      .map((item) => ({ groupKey: group.key, item })),
  );
  const match = matchingItems.sort((left, right) => right.item.href.length - left.item.href.length)[0];

  if (match) {
    return { groupKey: match.groupKey, itemKey: match.item.key };
  }

  return { groupKey: "market", itemKey: "overview" };
}

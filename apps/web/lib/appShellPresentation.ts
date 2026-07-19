export const APP_SHELL_COLLAPSED_STORAGE_KEY = "stockmaster:app-shell-collapsed";
const MAX_WORKSPACE_TABS = 12;
const WORKSPACE_ORIGIN = "https://stockmaster.local";

const WORKSPACE_LABELS: Record<string, string> = {
  "/": "市场总览",
  "/screener": "强势选股",
  "/auction": "竞价雷达",
  "/market": "板块与热图",
  "/watchlist": "自选与风险",
  "/sentiment": "情绪与复盘",
  "/chanlun": "缠论工作台",
  "/system": "模型与数据源",
};

export type WorkspaceTab = {
  closable: boolean;
  href: string;
  key: string;
  label: string;
};

export type AppShellStorage = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

export function readAppShellCollapsed(storage: AppShellStorage | null | undefined): boolean {
  try {
    return storage?.getItem(APP_SHELL_COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function toggleAppShellCollapsed(collapsed: boolean, storage: AppShellStorage | null | undefined): boolean {
  const next = !collapsed;

  try {
    storage?.setItem(APP_SHELL_COLLAPSED_STORAGE_KEY, String(next));
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }

  return next;
}

export function resolveMobileNavigationOpen(mobileNavigationOpen: boolean, matchesDesktop: boolean): boolean {
  return matchesDesktop ? false : mobileNavigationOpen;
}

export function buildWorkspaceTab(pathname: string, search: string): WorkspaceTab {
  const normalizedPathname = pathname || "/";
  const normalizedSearch = search ? (search.startsWith("?") ? search : `?${search}`) : "";
  const href = `${normalizedPathname}${normalizedSearch}`;
  const stockSymbol = normalizedPathname.startsWith("/stock/")
    ? normalizedPathname.slice("/stock/".length).split("/")[0]
    : "";
  const label = stockSymbol
    ? `个股 ${stockSymbol}`
    : WORKSPACE_LABELS[normalizedPathname] ?? "工作区";

  return {
    closable: normalizedPathname !== "/",
    href,
    key: normalizedPathname,
    label,
  };
}

export function upsertWorkspaceTab(tabs: WorkspaceTab[], tab: WorkspaceTab): WorkspaceTab[] {
  const existingIndex = tabs.findIndex((item) => item.key === tab.key);
  if (existingIndex >= 0) {
    const existing = tabs[existingIndex];
    if (
      existing?.href === tab.href
      && existing.label === tab.label
      && existing.closable === tab.closable
    ) {
      return tabs;
    }
    return tabs.map((item, index) => (index === existingIndex ? tab : item));
  }

  const nextTabs = [...tabs, tab];
  if (nextTabs.length <= MAX_WORKSPACE_TABS) {
    return nextTabs;
  }
  const oldestClosableIndex = nextTabs.findIndex((item) => item.closable);
  return nextTabs.filter((_, index) => index !== oldestClosableIndex);
}

export function restoreWorkspaceTabs(serialized: string | null | undefined): WorkspaceTab[] {
  if (!serialized) {
    return [];
  }
  try {
    const parsed = JSON.parse(serialized) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.reduce<WorkspaceTab[]>((tabs, value) => {
      if (!value || typeof value !== "object") {
        return tabs;
      }
      const href = (value as { href?: unknown }).href;
      const tab = typeof href === "string" ? workspaceTabFromHref(href) : null;
      return tab ? upsertWorkspaceTab(tabs, tab) : tabs;
    }, []);
  } catch {
    return [];
  }
}

export function closeWorkspaceTab(
  tabs: WorkspaceTab[],
  key: string,
  activeKey: string,
): { activeKey: string; tabs: WorkspaceTab[] } {
  const closingIndex = tabs.findIndex((tab) => tab.key === key);
  const closingTab = tabs[closingIndex];
  if (closingIndex < 0 || !closingTab?.closable) {
    return { activeKey, tabs };
  }

  const remainingTabs = tabs.filter((tab) => tab.key !== key);
  if (key !== activeKey) {
    return { activeKey, tabs: remainingTabs };
  }

  const fallbackTab = remainingTabs[Math.max(0, closingIndex - 1)] ?? remainingTabs[0];
  return {
    activeKey: fallbackTab?.key ?? "/",
    tabs: remainingTabs,
  };
}

function workspaceTabFromHref(href: string): WorkspaceTab | null {
  if (!href.startsWith("/") || href.startsWith("//")) {
    return null;
  }
  const url = new URL(href, WORKSPACE_ORIGIN);
  if (url.origin !== WORKSPACE_ORIGIN || url.hash) {
    return null;
  }
  return buildWorkspaceTab(url.pathname, url.search);
}

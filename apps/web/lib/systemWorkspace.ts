export const SYSTEM_TABS = ["model", "data"] as const;

export type SystemTab = (typeof SYSTEM_TABS)[number];

export function normalizeSystemTab(value: unknown): SystemTab {
  return value === "data" ? "data" : "model";
}

export function createVisitedSystemTabs(currentTab: SystemTab): SystemTab[] {
  return [currentTab];
}

export function visitSystemTab(visitedTabs: SystemTab[], tab: SystemTab): SystemTab[] {
  return visitedTabs.includes(tab) ? visitedTabs : [...visitedTabs, tab];
}

export function buildSystemTabHref(tab: SystemTab): string {
  return "/system?tab=" + tab;
}

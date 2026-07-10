export const APP_SHELL_COLLAPSED_STORAGE_KEY = "stockmaster:app-shell-collapsed";

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

"use client";

import {
  AppstoreOutlined,
  BarChartOutlined,
  CloseOutlined,
  FolderOpenOutlined,
  FundOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  ReloadOutlined,
  RiseOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Tooltip } from "antd";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  getNavigationSelection,
  navigationGroups,
  type NavigationItemKey,
} from "../lib/appNavigation";
import {
  buildWorkspaceTab,
  closeWorkspaceTab,
  readAppShellCollapsed,
  restoreWorkspaceTabs,
  resolveMobileNavigationOpen,
  toggleAppShellCollapsed,
  upsertWorkspaceTab,
  type WorkspaceTab,
} from "../lib/appShellPresentation";
import { joinClassNames } from "../lib/workbenchPresentation";

const navigationIcons: Record<NavigationItemKey, ReactNode> = {
  overview: <AppstoreOutlined />,
  screener: <BarChartOutlined />,
  auction: <RiseOutlined />,
  market: <LineChartOutlined />,
  watchlist: <FolderOpenOutlined />,
  sentiment: <ThunderboltOutlined />,
  chanlun: <FundOutlined />,
  system: <SettingOutlined />,
};

const APP_SHELL_TABS_STORAGE_KEY = "stockmaster:workspace-tabs";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const currentTab = useMemo(() => buildWorkspaceTab(pathname, search), [pathname, search]);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [fullContent, setFullContent] = useState(false);
  const [tabs, setTabs] = useState<WorkspaceTab[]>([buildWorkspaceTab("/", "")]);

  useEffect(() => {
    setCollapsed(readAppShellCollapsed(getBrowserStorage()));
    const storedTabs = readWorkspaceTabs(getSessionStorage());
    if (storedTabs.length > 0) {
      setTabs(storedTabs);
    }
  }, []);

  useEffect(() => {
    setTabs((current) => upsertWorkspaceTab(current, currentTab));
  }, [currentTab]);

  useEffect(() => {
    try {
      getSessionStorage()?.setItem(APP_SHELL_TABS_STORAGE_KEY, JSON.stringify(tabs));
    } catch {
      // Session storage can be unavailable in private or restricted browser contexts.
    }
  }, [tabs]);

  useEffect(() => {
    const desktopMediaQuery = window.matchMedia("(min-width: 980px)");
    const handleDesktopViewportChange = () => {
      setMobileNavigationOpen((current) => resolveMobileNavigationOpen(current, desktopMediaQuery.matches));
    };

    handleDesktopViewportChange();
    desktopMediaQuery.addEventListener("change", handleDesktopViewportChange);
    return () => desktopMediaQuery.removeEventListener("change", handleDesktopViewportChange);
  }, []);

  function toggleCollapsed() {
    setCollapsed((current) => toggleAppShellCollapsed(current, getBrowserStorage()));
  }

  function closeTab(key: string) {
    const result = closeWorkspaceTab(tabs, key, currentTab.key);
    setTabs(result.tabs);
    if (result.activeKey !== currentTab.key) {
      router.push(result.tabs.find((tab) => tab.key === result.activeKey)?.href ?? "/");
    }
  }

  return (
    <Layout className={joinClassNames("app-shell", fullContent && "app-shell--full-content")} hasSider>
      <Layout.Sider
        className="app-shell__desktop-nav"
        collapsed={collapsed}
        collapsedWidth={64}
        trigger={null}
        width={220}
      >
        <div
          className={joinClassNames(
            "app-shell__desktop-sidebar",
            collapsed && "app-shell__desktop-sidebar--collapsed",
          )}
        >
          <ProductMark collapsed={collapsed} />
          <ShellNavigation collapsed={collapsed} pathname={pathname} />
          <div className="app-shell__sidebar-footer">
            <Tooltip title={collapsed ? "展开导航" : "收起导航"}>
              <Button
                aria-label={collapsed ? "展开导航" : "收起导航"}
                className="app-shell__collapse-button"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={toggleCollapsed}
                type="text"
              />
            </Tooltip>
          </div>
        </div>
      </Layout.Sider>
      <Layout className="app-shell__main">
        <AppShellHeader
          collapsed={collapsed}
          currentTab={currentTab}
          fullContent={fullContent}
          onFullContent={() => setFullContent((current) => !current)}
          onMobileNavigation={() => setMobileNavigationOpen(true)}
          onReload={() => window.location.reload()}
          onToggleCollapsed={toggleCollapsed}
        />
        <WorkspaceTabs currentKey={currentTab.key} onClose={closeTab} onNavigate={(href) => router.push(href)} tabs={tabs} />
        {children}
      </Layout>
      <Drawer
        aria-label="主导航"
        className="app-shell__drawer"
        closable={false}
        onClose={() => setMobileNavigationOpen(false)}
        open={mobileNavigationOpen}
        placement="left"
        title={null}
      >
        <div className="app-shell__drawer-content">
          <ProductMark />
          <ShellNavigation pathname={pathname} onNavigate={() => setMobileNavigationOpen(false)} />
        </div>
      </Drawer>
    </Layout>
  );
}

function AppShellHeader({
  collapsed,
  currentTab,
  fullContent,
  onFullContent,
  onMobileNavigation,
  onReload,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  currentTab: WorkspaceTab;
  fullContent: boolean;
  onFullContent: () => void;
  onMobileNavigation: () => void;
  onReload: () => void;
  onToggleCollapsed: () => void;
}) {
  return (
    <header className="app-shell__header">
      <div className="app-shell__header-leading">
        <Button
          aria-label="打开导航"
          className="app-shell__mobile-menu"
          icon={<MenuOutlined />}
          onClick={onMobileNavigation}
          type="text"
        />
        <Button
          aria-label={collapsed ? "展开导航" : "收起导航"}
          className="app-shell__desktop-menu"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={onToggleCollapsed}
          type="text"
        />
        <Link aria-label="StockMaster" className="app-shell__mobile-brand" href="/">
          <span aria-hidden="true" className="app-shell__mark">S</span>
          <span>StockMaster</span>
        </Link>
        <div aria-label="当前位置" className="app-shell__breadcrumbs">
          <span>工作台</span>
          <span aria-hidden="true" className="app-shell__breadcrumb-separator">/</span>
          <strong>{currentTab.label}</strong>
        </div>
      </div>
      <div className="app-shell__header-tools">
        <Tooltip title="刷新当前工作区">
          <Button aria-label="刷新当前工作区" icon={<ReloadOutlined />} onClick={onReload} type="text" />
        </Tooltip>
        <Tooltip title={fullContent ? "退出沉浸布局" : "沉浸布局"}>
          <Button
            aria-label={fullContent ? "退出沉浸布局" : "沉浸布局"}
            icon={fullContent ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={onFullContent}
            type="text"
          />
        </Tooltip>
      </div>
    </header>
  );
}

function WorkspaceTabs({
  currentKey,
  onClose,
  onNavigate,
  tabs,
}: {
  currentKey: string;
  onClose: (key: string) => void;
  onNavigate: (href: string) => void;
  tabs: WorkspaceTab[];
}) {
  return (
    <nav aria-label="工作区标签" className="app-shell__tabs">
      <div className="app-shell__tabs-scroll">
        {tabs.map((tab) => {
          const active = tab.key === currentKey;
          return (
            <div className={joinClassNames("app-shell__tab", active && "app-shell__tab--active")} key={tab.key}>
              <button
                aria-current={active ? "page" : undefined}
                className="app-shell__tab-button"
                onClick={() => onNavigate(tab.href)}
                type="button"
              >
                {tab.label}
              </button>
              {tab.closable ? (
                <button
                  aria-label={`关闭${tab.label}`}
                  className="app-shell__tab-close"
                  onClick={() => onClose(tab.key)}
                  type="button"
                >
                  <CloseOutlined aria-hidden="true" />
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function getBrowserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function getSessionStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function readWorkspaceTabs(storage: Storage | null): WorkspaceTab[] {
  try {
    return restoreWorkspaceTabs(storage?.getItem(APP_SHELL_TABS_STORAGE_KEY));
  } catch {
    return [];
  }
}

function ProductMark({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <Link aria-label="StockMaster" className="app-shell__brand" href="/">
      <span aria-hidden="true" className="app-shell__mark">
        S
      </span>
      {collapsed ? <span className="sr-only">StockMaster</span> : <span className="app-shell__brand-name">StockMaster</span>}
    </Link>
  );
}

function ShellNavigation({
  collapsed = false,
  onNavigate,
  pathname,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
  pathname: string;
}) {
  const selection = getNavigationSelection(pathname);

  return (
    <nav aria-label="主导航" className="app-shell__navigation">
      {navigationGroups.map((group) => (
        <section
          className={joinClassNames(
            "app-shell__navigation-group",
            selection.groupKey === group.key && "app-shell__navigation-group--active",
          )}
          key={group.key}
        >
          {collapsed ? null : <h2 className="app-shell__navigation-group-label">{group.label}</h2>}
          <div className="app-shell__navigation-items">
            {group.items.map((item) => {
              const active = selection.itemKey === item.key;

              return (
                <Tooltip key={item.key} placement="right" title={collapsed ? item.label : undefined}>
                  <Link
                    aria-current={active ? "page" : undefined}
                    aria-label={item.label}
                    className={joinClassNames(
                      "app-shell__navigation-link",
                      collapsed && "app-shell__navigation-link--collapsed",
                      active && "app-shell__navigation-link--active",
                    )}
                    href={item.href}
                    onClick={onNavigate}
                  >
                    <span aria-hidden="true" className="app-shell__navigation-icon">
                      {navigationIcons[item.key]}
                    </span>
                    {collapsed ? null : <span className="app-shell__navigation-label">{item.label}</span>}
                  </Link>
                </Tooltip>
              );
            })}
          </div>
        </section>
      ))}
    </nav>
  );
}

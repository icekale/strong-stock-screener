"use client";

import {
  AppstoreOutlined,
  BarChartOutlined,
  FolderOpenOutlined,
  FundOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  RiseOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Layout, Tooltip } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  getNavigationSelection,
  navigationGroups,
  type NavigationItemKey,
} from "../lib/appNavigation";
import {
  readAppShellCollapsed,
  resolveMobileNavigationOpen,
  toggleAppShellCollapsed,
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

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  useEffect(() => {
    setCollapsed(readAppShellCollapsed(getBrowserStorage()));
  }, []);

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

  return (
    <Layout className="app-shell" hasSider>
      <Layout.Sider
        className="app-shell__desktop-nav"
        collapsed={collapsed}
        collapsedWidth={64}
        trigger={null}
        width={216}
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
        <header className="app-shell__mobile-header">
          <Button
            aria-label="打开导航"
            icon={<MenuOutlined />}
            onClick={() => setMobileNavigationOpen(true)}
            type="text"
          />
          <Link aria-label="StockMaster" className="app-shell__mobile-brand" href="/">
            <span aria-hidden="true" className="app-shell__mark">
              S
            </span>
            <span>StockMaster</span>
          </Link>
        </header>
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

function getBrowserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
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

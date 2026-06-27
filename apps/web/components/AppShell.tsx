"use client";

import {
  BarChartOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  SettingOutlined,
  StarOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import type { MenuProps } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";

type MenuItem = NonNullable<MenuProps["items"]>[number];

const NAV_ITEMS: MenuItem[] = [
  {
    key: "/",
    icon: <BarChartOutlined />,
    label: <Link href="/">选股工作台</Link>,
  },
  {
    key: "/watchlist",
    icon: <StarOutlined />,
    label: <Link href="/watchlist">自选股管理</Link>,
  },
  {
    key: "/settings",
    icon: <SettingOutlined />,
    label: <Link href="/settings">数据源配置</Link>,
  },
];

const STOCK_NAV_ITEMS: MenuItem[] = [
  {
    key: "/stock",
    icon: <LineChartOutlined />,
    label: "个股详情",
    disabled: true,
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const selectedKey = selectedNavKey(pathname);
  const items = pathname.startsWith("/stock/") ? [...NAV_ITEMS, ...STOCK_NAV_ITEMS] : NAV_ITEMS;

  return (
    <Layout className="app-shell min-h-screen bg-slate-50">
      <Layout.Sider
        breakpoint="lg"
        collapsedWidth={0}
        className="app-shell__sider border-r border-slate-200"
        width={224}
      >
        <div className="border-b border-slate-100 px-4 py-4">
          <div className="flex items-center gap-2">
            <DatabaseOutlined className="text-base text-slate-950" />
            <Typography.Text className="text-sm font-black text-slate-950">强势股选股</Typography.Text>
          </div>
          <Typography.Text className="mt-1 block text-xs font-semibold text-slate-500">
            独立选股工作台
          </Typography.Text>
        </div>
        <Menu
          className="border-none px-2 py-3"
          items={items}
          mode="inline"
          selectedKeys={[selectedKey]}
        />
      </Layout.Sider>
      <Layout className="min-w-0 bg-slate-50">{children}</Layout>
    </Layout>
  );
}

function selectedNavKey(pathname: string): string {
  if (pathname.startsWith("/watchlist")) {
    return "/watchlist";
  }
  if (pathname.startsWith("/settings")) {
    return "/settings";
  }
  if (pathname.startsWith("/stock/")) {
    return "/stock";
  }
  return "/";
}

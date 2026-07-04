"use client";

import {
  BarChartOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  FundProjectionScreenOutlined,
  ThunderboltOutlined,
  LineChartOutlined,
  RiseOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Layout, Tooltip, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  icon: React.ReactNode;
  key: string;
  label: string;
  title: string;
};

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    key: "/",
    icon: <BarChartOutlined />,
    label: "选股",
    title: "选股工作台",
  },
  {
    href: "/watchlist",
    key: "/watchlist",
    icon: <FolderOpenOutlined />,
    label: "自选",
    title: "自选股管理",
  },
  {
    href: "/sectors",
    key: "/sectors",
    icon: <FundProjectionScreenOutlined />,
    label: "板块",
    title: "板块资金流",
  },
  {
    href: "/auction",
    key: "/auction",
    icon: <RiseOutlined />,
    label: "竞价",
    title: "竞价雷达",
  },
  {
    href: "/sentiment",
    key: "/sentiment",
    icon: <ThunderboltOutlined />,
    label: "情绪",
    title: "短线情绪",
  },
  {
    href: "/model-maintenance",
    key: "/model-maintenance",
    icon: <ExperimentOutlined />,
    label: "模型",
    title: "模型维护",
  },
  {
    href: "/settings",
    key: "/settings",
    icon: <SettingOutlined />,
    label: "设置",
    title: "数据源配置",
  },
];

const STOCK_NAV_ITEMS: NavItem[] = [
  {
    href: "#",
    key: "/stock",
    icon: <LineChartOutlined />,
    label: "个股",
    title: "个股详情",
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const selectedKey = selectedNavKey(pathname);
  const items = pathname.startsWith("/stock/") ? [...NAV_ITEMS, ...STOCK_NAV_ITEMS] : NAV_ITEMS;

  return (
    <Layout className="app-shell min-h-screen bg-[#f5f3f0]">
      <Layout.Sider
        className="app-shell__sider border-r border-[#2b2925] bg-[#1d1b18]"
        width={68}
      >
        <div className="flex h-full flex-col items-center bg-[#1d1b18] py-5 text-white">
          <Tooltip placement="right" title="StockMaster · 强势股选股工作台">
            <Link
              aria-label="StockMaster 强势股选股工作台"
              className="flex size-9 items-center justify-center rounded-lg bg-[#f04438] text-sm font-black text-white"
              href="/"
            >
              S
            </Link>
          </Tooltip>
          <span className="sr-only">StockMaster</span>
          <nav className="mt-9 flex flex-1 flex-col items-center gap-4">
            {items.map((item) => {
              const active = selectedKey === item.key;
              const isDisabled = item.key === "/stock" && !pathname.startsWith("/stock/");
              const content = (
                <span
                  className={`flex size-12 flex-col items-center justify-center rounded-lg text-[10px] font-semibold transition ${
                    active
                      ? "bg-[#34312d] text-white"
                      : "text-[#8c8780] hover:bg-[#282520] hover:text-white"
                  } ${isDisabled ? "cursor-not-allowed opacity-40" : ""}`}
                >
                  <span className="text-lg leading-none">{item.icon}</span>
                  <span className="mt-1 leading-none">{item.label}</span>
                </span>
              );
              return (
                <Tooltip key={item.key} placement="right" title={item.title}>
                  {isDisabled ? (
                    content
                  ) : (
                    <Link aria-label={item.title} href={item.href}>
                      {content}
                    </Link>
                  )}
                </Tooltip>
              );
            })}
          </nav>
          <div className="flex flex-col items-center gap-4 border-t border-[#34312d] pt-4">
            <Tooltip placement="right" title="数据源配置">
              <Link
                aria-label="数据源配置"
                className="flex size-10 items-center justify-center rounded-lg text-[#8c8780] transition hover:bg-[#282520] hover:text-white"
                href="/settings"
              >
                <DatabaseOutlined />
              </Link>
            </Tooltip>
            <Tooltip placement="right" title="系统设置">
              <Link
                aria-label="系统设置"
                className="flex size-10 items-center justify-center rounded-lg text-[#8c8780] transition hover:bg-[#282520] hover:text-white"
                href="/settings"
              >
                <SettingOutlined />
              </Link>
            </Tooltip>
            <Typography.Text className="text-[10px] font-black text-[#706b63]">A股</Typography.Text>
          </div>
        </div>
      </Layout.Sider>
      <Layout className="min-w-0 bg-[#f5f3f0]">{children}</Layout>
    </Layout>
  );
}

function selectedNavKey(pathname: string): string {
  if (pathname.startsWith("/watchlist")) {
    return "/watchlist";
  }
  if (pathname.startsWith("/sectors")) {
    return "/sectors";
  }
  if (pathname.startsWith("/auction")) {
    return "/auction";
  }
  if (pathname.startsWith("/sentiment")) {
    return "/sentiment";
  }
  if (pathname.startsWith("/model-maintenance")) {
    return "/model-maintenance";
  }
  if (pathname.startsWith("/settings")) {
    return "/settings";
  }
  if (pathname.startsWith("/stock/")) {
    return "/stock";
  }
  return "/";
}

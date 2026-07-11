"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { PageFrame } from "../components/workbench/PageFrame";

const MarketOverviewWorkbench = dynamic(
  () => import("./MarketOverviewWorkbench").then((module) => module.MarketOverviewWorkbench),
  { ssr: false, loading: () => <MarketOverviewPlaceholder /> },
) as ComponentType;

export default function HomePage() {
  return <MarketOverviewWorkbench />;
}

function MarketOverviewPlaceholder() {
  return (
    <PageFrame context="正在读取上海市场数据" title="市场总览">
      <div className="market-overview-layout">
        <div className="market-overview-lead">
          <PlaceholderPanel rows={5} title="板块资金流" />
          <PlaceholderPanel rows={5} title="市场状态" />
        </div>
        <PlaceholderPanel rows={1} title="指数快照" />
      </div>
    </PageFrame>
  );
}

function PlaceholderPanel({ rows, title }: { rows: number; title: string }) {
  return (
    <section className="compact-panel">
      <div className="compact-panel__header">
        <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]">{title}</h2>
      </div>
      <div className="p-4">
        <Skeleton active paragraph={{ rows }} title={false} />
      </div>
    </section>
  );
}

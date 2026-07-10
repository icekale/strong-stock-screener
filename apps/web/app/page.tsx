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
      <div className="grid gap-4 xl:grid-cols-2">
        {["决策队列", "市场脉冲", "板块资金流", "市场动态"].map((title) => (
          <section className="compact-panel" key={title}>
            <div className="compact-panel__header">
              <h2 className="m-0 text-sm font-semibold text-[var(--app-ink)]">{title}</h2>
            </div>
            <div className="p-4">
              <Skeleton active paragraph={{ rows: title === "决策队列" ? 7 : 4 }} title={false} />
            </div>
          </section>
        ))}
      </div>
    </PageFrame>
  );
}

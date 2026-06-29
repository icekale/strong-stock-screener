"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const HomeWorkbench = dynamic(
  () => import("./HomeWorkbench").then((module) => module.HomeWorkbench),
  { ssr: false, loading: () => <HomeWorkbenchPlaceholder /> },
) as ComponentType;

export default function HomePage() {
  return <HomeWorkbench />;
}

function HomeWorkbenchPlaceholder() {
  return (
    <main className="min-h-screen bg-[#f5f3f0] text-[#11100e]">
      <div className="mx-auto max-w-none space-y-4 px-5 py-4">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {["总成交额 TOTAL TURNOVER", "情绪指数", "涨跌比", "数据源"].map((title) => (
            <Card className="workbench-card" key={title}>
              <Typography.Text className="text-xs font-black uppercase text-[#7b756d]">{title}</Typography.Text>
              <Skeleton active paragraph={{ rows: 2 }} title={false} />
            </Card>
          ))}
        </section>
        <Card className="workbench-card">
          <Typography.Title className="text-base font-black text-[#11100e]" level={2}>
            选股结果 · Screener Results
          </Typography.Title>
          <Skeleton active paragraph={{ rows: 10 }} title={false} />
        </Card>
      </div>
    </main>
  );
}

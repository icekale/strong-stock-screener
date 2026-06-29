"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const SentimentWorkspace = dynamic(
  () => import("./SentimentWorkspace").then((module) => module.SentimentWorkspace),
  { ssr: false, loading: () => <SentimentWorkspacePlaceholder /> },
) as ComponentType;

export default function SentimentPage() {
  return <SentimentWorkspace />;
}

function SentimentWorkspacePlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          短线情绪中心
        </Typography.Title>
        <Typography.Text className="workbench-muted">
          正在加载涨停池、炸板池、连板天梯和盘中情绪。
        </Typography.Text>
      </div>
      <div className="space-y-4">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {["市场情绪仪表盘", "情绪指标", "亏钱效应", "今日封板率"].map((title) => (
            <Card className="workbench-panel" key={title} size="small">
              <Typography.Text className="text-xs font-black text-[#7b756d]">{title}</Typography.Text>
              <Skeleton active paragraph={{ rows: 2 }} title={false} />
            </Card>
          ))}
        </section>
        <Card className="workbench-panel">
          <Skeleton active paragraph={{ rows: 12 }} />
        </Card>
      </div>
    </main>
  );
}

"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";

const SentimentWorkspace = dynamic(
  () => import("./SentimentWorkspace").then((module) => module.SentimentWorkspace),
  { ssr: false, loading: () => <SentimentWorkspacePlaceholder /> },
) as ComponentType;

export default function SentimentPage() {
  return <SentimentWorkspace />;
}

function SentimentWorkspacePlaceholder() {
  return (
    <PageFrame context="正在加载涨停池、炸板池、连板天梯和盘中情绪。" title="短线情绪中心">
      <div aria-busy="true" aria-label="正在加载短线情绪中心" className="space-y-4">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {["市场情绪仪表盘", "情绪指标", "亏钱效应", "今日封板率"].map((title) => (
            <section className="compact-panel p-4" key={title}>
              <span className="text-xs font-black text-[var(--app-muted)]">{title}</span>
              <Skeleton active paragraph={{ rows: 2 }} title={false} />
            </section>
          ))}
        </section>
        <section className="compact-panel p-4">
          <Skeleton active paragraph={{ rows: 12 }} />
        </section>
      </div>
    </PageFrame>
  );
}

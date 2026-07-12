"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";

const ChanlunWorkspace = dynamic(
  () => import("./ChanlunWorkspace").then((module) => module.ChanlunWorkspace),
  { ssr: false, loading: () => <ChanlunWorkspacePlaceholder /> },
) as ComponentType;

export default function ChanlunPage() {
  return <ChanlunWorkspace />;
}

function ChanlunWorkspacePlaceholder() {
  return (
    <PageFrame context="正在加载多周期结构和K线图。" title="缠论工作台">
      <div aria-busy="true" aria-label="正在加载缠论工作台" className="space-y-4">
        <section className="compact-panel p-4">
          <Skeleton active paragraph={{ rows: 1 }} title={false} />
        </section>
        <section className="compact-panel p-4">
          <Skeleton active paragraph={{ rows: 9 }} title={false} />
        </section>
      </div>
    </PageFrame>
  );
}

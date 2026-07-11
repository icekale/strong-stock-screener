"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";

const WatchlistWorkspace = dynamic(
  () => import("./WatchlistWorkspace").then((module) => module.WatchlistWorkspace),
  { ssr: false, loading: () => <WatchlistWorkspacePlaceholder /> },
) as ComponentType;

export default function WatchlistPage() {
  return <WatchlistWorkspace />;
}

function WatchlistWorkspacePlaceholder() {
  return (
    <PageFrame context="正在加载分组、标签和观察池。" title="自选股管理">
        <div aria-busy="true" aria-label="正在加载自选股管理" className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <section className="compact-panel p-4">
            <Skeleton active paragraph={{ rows: 10 }} />
          </section>
          <section className="compact-panel min-w-0 p-4">
            <Skeleton active paragraph={{ rows: 12 }} />
          </section>
          <section className="compact-panel p-4">
            <Skeleton active paragraph={{ rows: 8 }} />
          </section>
        </div>
    </PageFrame>
  );
}

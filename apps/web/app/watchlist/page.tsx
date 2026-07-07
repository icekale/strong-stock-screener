"use client";

import { Card, Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";

const WatchlistWorkspace = dynamic(
  () => import("./WatchlistWorkspace").then((module) => module.WatchlistWorkspace),
  { ssr: false, loading: () => <WatchlistWorkspacePlaceholder /> },
) as ComponentType;

export default function WatchlistPage() {
  return <WatchlistWorkspace />;
}

function WatchlistWorkspacePlaceholder() {
  return (
    <WorkbenchPage
      description="正在加载分组、标签和观察池。"
      eyebrow="Watchlist"
      title="自选股管理"
    >
        <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)_320px]">
          <Card className="workbench-panel" size="small">
            <Skeleton active paragraph={{ rows: 10 }} />
          </Card>
          <Card className="workbench-panel min-w-0">
            <Skeleton active paragraph={{ rows: 12 }} />
          </Card>
          <Card className="workbench-panel">
            <Skeleton active paragraph={{ rows: 8 }} />
          </Card>
        </div>
    </WorkbenchPage>
  );
}

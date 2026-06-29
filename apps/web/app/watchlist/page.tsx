"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const WatchlistWorkspace = dynamic(
  () => import("./WatchlistWorkspace").then((module) => module.WatchlistWorkspace),
  { ssr: false, loading: () => <WatchlistWorkspacePlaceholder /> },
) as ComponentType;

export default function WatchlistPage() {
  return <WatchlistWorkspace />;
}

function WatchlistWorkspacePlaceholder() {
  return (
    <main className="workbench-page">
      <div className="mx-auto max-w-none space-y-4 px-5 py-4">
        <Card className="workbench-panel" styles={{ body: { padding: 18 } }}>
          <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Watchlist</Typography.Text>
          <Typography.Title className="workbench-ink mt-1 text-2xl font-black tracking-tight" level={1}>
            自选股管理
          </Typography.Title>
          <Typography.Text className="workbench-muted mt-1 block text-sm font-medium">
            正在加载分组、标签和观察池。
          </Typography.Text>
        </Card>
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
      </div>
    </main>
  );
}

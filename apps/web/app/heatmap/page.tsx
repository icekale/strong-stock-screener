"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const HeatmapWorkspace = dynamic(
  () => import("./HeatmapWorkspace").then((module) => module.HeatmapWorkspace),
  { ssr: false, loading: () => <HeatmapWorkspacePlaceholder /> },
) as ComponentType;

export default function HeatmapPage() {
  return <HeatmapWorkspace />;
}

function HeatmapWorkspacePlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          市场热力图
        </Typography.Title>
        <Typography.Text className="workbench-muted">
          正在加载全 A 行业热图和行情状态。
        </Typography.Text>
      </div>
      <section className="grid gap-4 xl:grid-cols-[264px_minmax(0,1fr)_300px]">
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 9 }} title={false} />
        </Card>
        <Card className="workbench-panel min-h-[560px] min-w-0" styles={{ body: { padding: 0 } }}>
          <Skeleton active className="p-4" paragraph={{ rows: 12 }} />
        </Card>
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      </section>
    </main>
  );
}

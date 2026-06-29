"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const SectorPageWorkspace = dynamic(
  () => import("./SectorPageWorkspace").then((module) => module.SectorPageWorkspace),
  { ssr: false, loading: () => <SectorFlowPlaceholder /> },
) as ComponentType;

export default function SectorsPage() {
  return <SectorPageWorkspace />;
}

function SectorFlowPlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          板块资金流
        </Typography.Title>
        <Typography.Text className="workbench-muted">
          正在加载全市场板块热度、成交额和涨跌额。
        </Typography.Text>
      </div>
      <section className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 9 }} title={false} />
        </Card>
        <Card className="workbench-panel min-w-0">
          <Skeleton active paragraph={{ rows: 12 }} />
        </Card>
      </section>
    </main>
  );
}

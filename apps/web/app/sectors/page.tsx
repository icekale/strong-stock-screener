"use client";

import { Card, Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";

const SectorPageWorkspace = dynamic(
  () => import("./SectorPageWorkspace").then((module) => module.SectorPageWorkspace),
  { ssr: false, loading: () => <SectorFlowPlaceholder /> },
) as ComponentType;

export default function SectorsPage() {
  return <SectorPageWorkspace />;
}

function SectorFlowPlaceholder() {
  return (
    <WorkbenchPage
      description="正在加载全市场板块热度、成交额和涨跌额。"
      title="行业强度工作台"
    >
      <section className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 9 }} title={false} />
        </Card>
        <Card className="workbench-panel min-w-0">
          <Skeleton active paragraph={{ rows: 12 }} />
        </Card>
      </section>
    </WorkbenchPage>
  );
}

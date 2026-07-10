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
    <WorkbenchPage contentClassName="sector-replica-page-content">
      <section className="grid min-h-[calc(100vh-24px)] grid-cols-[226px_minmax(0,1fr)] overflow-hidden rounded-lg border border-[#ddd8d0] bg-[#f8f7f4] max-[980px]:grid-cols-1">
        <Card className="workbench-panel" size="small">
          <Skeleton active paragraph={{ rows: 14 }} title={false} />
        </Card>
        <Card className="workbench-panel min-w-0 border-0">
          <Skeleton active paragraph={{ rows: 12 }} />
        </Card>
      </section>
    </WorkbenchPage>
  );
}

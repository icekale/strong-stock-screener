"use client";

import { Card, Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";

const AuctionWorkspace = dynamic(
  () => import("./AuctionWorkspace").then((module) => module.AuctionWorkspace),
  { ssr: false, loading: () => <AuctionWorkspacePlaceholder /> },
) as ComponentType;

export default function AuctionPage() {
  return <AuctionWorkspace />;
}

function AuctionWorkspacePlaceholder() {
  return (
    <WorkbenchPage
      description="正在加载 TickFlow 早盘竞价快照。"
      title="竞价雷达"
    >
      <Card className="workbench-panel">
        <Skeleton active paragraph={{ rows: 12 }} />
      </Card>
    </WorkbenchPage>
  );
}

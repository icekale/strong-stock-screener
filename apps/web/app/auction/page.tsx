"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const AuctionWorkspace = dynamic(
  () => import("./AuctionWorkspace").then((module) => module.AuctionWorkspace),
  { ssr: false, loading: () => <AuctionWorkspacePlaceholder /> },
) as ComponentType;

export default function AuctionPage() {
  return <AuctionWorkspace />;
}

function AuctionWorkspacePlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          竞价雷达
        </Typography.Title>
        <Typography.Text className="workbench-muted">
          正在加载 TickFlow 早盘竞价快照。
        </Typography.Text>
      </div>
      <Card className="workbench-panel">
        <Skeleton active paragraph={{ rows: 12 }} />
      </Card>
    </main>
  );
}

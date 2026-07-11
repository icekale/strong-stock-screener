"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";

const AuctionWorkspace = dynamic(
  () => import("./AuctionWorkspace").then((module) => module.AuctionWorkspace),
  { ssr: false, loading: () => <AuctionWorkspacePlaceholder /> },
) as ComponentType;

export default function AuctionPage() {
  return <AuctionWorkspace />;
}

function AuctionWorkspacePlaceholder() {
  return (
    <PageFrame context="正在加载 TickFlow 早盘竞价快照。" title="竞价雷达">
      <section aria-busy="true" aria-label="正在加载竞价雷达" className="compact-panel p-4">
        <Skeleton active paragraph={{ rows: 12 }} />
      </section>
    </PageFrame>
  );
}

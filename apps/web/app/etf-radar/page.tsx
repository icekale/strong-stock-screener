"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { PageFrame } from "../../components/workbench/PageFrame";

const EtfRadarWorkspace = dynamic(
  () => import("./EtfRadarWorkspace").then((module) => module.EtfRadarWorkspace),
  { ssr: false, loading: () => <EtfRadarPlaceholder /> },
);

export default function EtfRadarPage() {
  return <EtfRadarWorkspace />;
}

function EtfRadarPlaceholder() {
  return (
    <PageFrame context="正在读取交易所资金数据" title="ETF资金雷达">
      <section className="compact-panel p-5"><Skeleton active paragraph={{ rows: 8 }} title={false} /></section>
    </PageFrame>
  );
}

"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const ModelMaintenanceWorkspace = dynamic(
  () => import("./ModelMaintenanceWorkspace").then((module) => module.ModelMaintenanceWorkspace),
  { ssr: false, loading: () => <ModelMaintenanceWorkspacePlaceholder /> },
) as ComponentType;

export default function ModelMaintenancePage() {
  return <ModelMaintenanceWorkspace />;
}

function ModelMaintenanceWorkspacePlaceholder() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4">
        <Typography.Text className="workbench-muted text-xs font-semibold uppercase">
          Model Maintenance
        </Typography.Text>
        <Typography.Title className="m-0 text-[#11100e]" level={3}>
          AI 模型维护
        </Typography.Title>
        <Typography.Text className="workbench-muted">
          正在加载股是股非模型复盘包、AI 分析和待确认建议。
        </Typography.Text>
      </div>
      <Card className="workbench-panel">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    </main>
  );
}

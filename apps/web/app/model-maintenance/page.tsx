"use client";

import { Card, Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";

const ModelMaintenanceWorkspace = dynamic(
  () => import("./ModelMaintenanceWorkspace").then((module) => module.ModelMaintenanceWorkspace),
  { ssr: false, loading: () => <ModelMaintenanceWorkspacePlaceholder /> },
) as ComponentType;

export default function ModelMaintenancePage() {
  return <ModelMaintenanceWorkspace />;
}

function ModelMaintenanceWorkspacePlaceholder() {
  return (
    <WorkbenchPage
      description="正在加载股是股非模型复盘包、AI 分析和待确认建议。"
      eyebrow="Model Maintenance"
      title="AI 模型维护"
    >
      <Card className="workbench-panel">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    </WorkbenchPage>
  );
}

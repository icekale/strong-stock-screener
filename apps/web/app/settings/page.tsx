"use client";

import { Card, Skeleton } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";
import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";

const SettingsWorkspace = dynamic(
  () => import("./SettingsWorkspace").then((module) => module.SettingsWorkspace),
  { ssr: false, loading: () => <SettingsWorkspacePlaceholder /> },
) as ComponentType;

export default function SettingsPage() {
  return <SettingsWorkspace />;
}

function SettingsWorkspacePlaceholder() {
  return (
    <WorkbenchPage
      description="正在读取独立选股工作台的数据源、模型和健康检查配置。"
      eyebrow="Settings"
      title="数据源配置"
    >
      <Card className="workbench-panel">
        <Skeleton active paragraph={{ rows: 8 }} title={false} />
      </Card>
    </WorkbenchPage>
  );
}

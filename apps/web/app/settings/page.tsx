"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { type ComponentType } from "react";

const SettingsWorkspace = dynamic(
  () => import("./SettingsWorkspace").then((module) => module.SettingsWorkspace),
  { ssr: false, loading: () => <SettingsWorkspacePlaceholder /> },
) as ComponentType;

export default function SettingsPage() {
  return <SettingsWorkspace />;
}

function SettingsWorkspacePlaceholder() {
  return (
    <main className="workbench-page">
      <div className="mx-auto max-w-none space-y-4 px-5 py-4">
        <Card className="workbench-panel">
          <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Settings</Typography.Text>
          <Typography.Title className="workbench-ink !mb-1 !mt-1 !text-2xl !font-black" level={1}>
            数据源配置
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            正在读取独立选股工作台的数据源、模型和健康检查配置。
          </Typography.Text>
        </Card>
        <Card className="workbench-panel">
          <Skeleton active paragraph={{ rows: 8 }} title={false} />
        </Card>
      </div>
    </main>
  );
}

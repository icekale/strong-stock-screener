"use client";

import { Typography } from "antd";
import { PlateReferencePanel } from "./PlateReferencePanel";
import { SectorThemeWorkbench } from "./SectorThemeWorkbench";

export function SectorPageWorkspace() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            行业强度工作台
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            默认使用行业指数口径，盘中对比板块强度和主力流入；稳定概念指数接入后再开放概念模式。
          </Typography.Text>
        </div>
      </div>

      <div className="mb-3">
        <PlateReferencePanel title="短线题材参考榜" />
      </div>

      <SectorThemeWorkbench />
    </main>
  );
}

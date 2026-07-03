"use client";

import { Typography } from "antd";
import { SectorThemeWorkbench } from "./SectorThemeWorkbench";

export function SectorPageWorkspace() {
  return (
    <main className="workbench-page min-h-screen p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title className="m-0 text-[#11100e]" level={3}>
            题材强度工作台
          </Typography.Title>
          <Typography.Text className="workbench-muted">
            概念/题材优先，行业辅助，盘中对比板块强度和主力流入。
          </Typography.Text>
        </div>
      </div>

      <SectorThemeWorkbench />
    </main>
  );
}

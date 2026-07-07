"use client";

import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";
import { PlateReferencePanel } from "./PlateReferencePanel";
import { SectorThemeWorkbench } from "./SectorThemeWorkbench";

export function SectorPageWorkspace() {
  return (
    <WorkbenchPage
      description="默认使用行业指数口径，盘中对比板块强度和主力流入；稳定概念指数接入后再开放概念模式。"
      title="行业强度工作台"
    >
      <div>
        <PlateReferencePanel title="短线题材参考榜" />
      </div>

      <SectorThemeWorkbench />
    </WorkbenchPage>
  );
}

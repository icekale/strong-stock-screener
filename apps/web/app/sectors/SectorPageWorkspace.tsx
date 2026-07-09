"use client";

import { WorkbenchPage } from "../../components/workbench/WorkbenchPage";
import { SectorReplicaWorkspace } from "./SectorReplicaWorkspace";

export function SectorPageWorkspace() {
  return (
    <WorkbenchPage contentClassName="sector-replica-page-content">
      <SectorReplicaWorkspace />
    </WorkbenchPage>
  );
}

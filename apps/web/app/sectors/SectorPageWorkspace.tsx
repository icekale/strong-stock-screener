import { SectorReplicaWorkspace } from "./SectorReplicaWorkspace";

export function SectorPageWorkspace() {
  return <SectorPageWorkspaceContent />;
}

export function SectorPageWorkspaceContent() {
  return (
    <div className="market-radar-page">
      <SectorReplicaWorkspace />
    </div>
  );
}

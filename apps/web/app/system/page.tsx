import { Skeleton } from "antd";
import { Suspense } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";
import { SystemWorkspace } from "./SystemWorkspace";

export default function SystemPage() {
  return (
    <Suspense fallback={<SystemWorkspaceFallback />}>
      <SystemWorkspace />
    </Suspense>
  );
}

function SystemWorkspaceFallback() {
  return (
    <PageFrame title="模型与数据源">
      <section aria-busy="true" className="app-panel p-4">
        <Skeleton active paragraph={{ rows: 8 }} />
      </section>
    </PageFrame>
  );
}

"use client";

import { Segmented, Space } from "antd";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { PageFrame } from "../../components/workbench/PageFrame";
import {
  buildSystemTabHref,
  createVisitedSystemTabs,
  normalizeSystemTab,
  visitSystemTab,
} from "../../lib/systemWorkspace";
import { ModelMaintenanceContent } from "../model-maintenance/ModelMaintenanceWorkspace";
import { SettingsContent } from "../settings/SettingsWorkspace";

const SYSTEM_TAB_OPTIONS = [
  { label: "模型维护", value: "model" },
  { label: "数据源", value: "data" },
];

export function SystemWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = normalizeSystemTab(searchParams.get("tab"));
  const [visitedTabs, setVisitedTabs] = useState(() => createVisitedSystemTabs(tab));

  useEffect(() => {
    setVisitedTabs((current) => visitSystemTab(current, tab));
  }, [tab]);

  function changeTab(value: string | number) {
    const next = normalizeSystemTab(value);
    if (next !== tab) {
      setVisitedTabs((current) => visitSystemTab(current, next));
      router.replace(buildSystemTabHref(next), { scroll: false });
    }
  }

  function renderPage(content: ReactNode, actions?: ReactNode) {
    return (
      <PageFrame
        actions={
          <Space wrap>
            <Segmented onChange={changeTab} options={SYSTEM_TAB_OPTIONS} value={tab} />
            {actions}
          </Space>
        }
        title="模型与数据源"
      >
        {content}
      </PageFrame>
    );
  }

  return (
    <>
      {visitedTabs.includes("model") ? (
        <div hidden={tab !== "model"}>
          <ModelMaintenanceContent renderPage={renderPage} />
        </div>
      ) : null}
      {visitedTabs.includes("data") ? (
        <div hidden={tab !== "data"}>
          <SettingsContent renderPage={(content, { actions }) => renderPage(content, actions)} />
        </div>
      ) : null}
    </>
  );
}

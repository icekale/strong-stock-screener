import { Empty, Tag, Typography } from "antd";
import type { CzscResearchSnapshot } from "../../lib/types";
import { groupCzscResearchEvidence } from "./chanlunWorkspaceHelpers";

const LABELS = { primary: "主信号", confirmation: "确认", risk: "风险", observation: "观察" } as const;

export function ChanlunResearchEvidence({ snapshot }: { snapshot: CzscResearchSnapshot | null }) {
  const groups = groupCzscResearchEvidence(snapshot);
  if (!snapshot || snapshot.status !== "ready") {
    return <Typography.Text type="secondary">{snapshot ? `研究引擎${snapshot.status}` : "研究信号加载中"}</Typography.Text>;
  }
  return (
    <div className="chanlun-research-evidence">
      {(Object.keys(LABELS) as Array<keyof typeof LABELS>).map((role) => (
        <section key={role}>
          <Typography.Text strong>{LABELS[role]}</Typography.Text>
          {groups[role].length ? groups[role].slice(-5).reverse().map((item) => (
            <div className="chanlun-research-evidence__item" key={item.id}>
              <Tag color={item.direction === "bullish" ? "green" : item.direction === "bearish" ? "red" : "default"}>{item.catalog_id}</Tag>
              <span>{item.signal_name}</span>
              <span>{item.occurred_at}</span>
            </div>
          )) : <Typography.Text type="secondary">暂无</Typography.Text>}
        </section>
      ))}
      {!snapshot.events.length ? <Empty description="暂无上游研究证据" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : null}
    </div>
  );
}

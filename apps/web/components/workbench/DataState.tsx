"use client";

import { Alert, Button, Empty, Skeleton } from "antd";
import { dataStateCopy } from "../../lib/workbenchPresentation";

export type DataStateKind = "loading" | "empty" | "stale" | "error";

type RecoveryAction = {
  label?: string;
  onClick: () => void;
};

type DataStateProps = {
  action?: RecoveryAction;
  kind: DataStateKind;
  subject?: string;
};

export function DataState({ action, kind, subject = "数据" }: DataStateProps) {
  if (kind === "loading") {
    return (
      <div aria-live="polite" className="data-state data-state--loading">
        <Skeleton active paragraph={{ rows: 3 }} title={false} />
      </div>
    );
  }

  if (kind === "empty") {
    const copy = dataStateCopy("empty", subject);

    return (
      <div className="data-state data-state--empty">
        <Empty
          description={
            <span>
              <strong>{copy.title}</strong>
              <span className="data-state__description">{copy.description}</span>
            </span>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          {action ? <RecoveryButton action={action} /> : null}
        </Empty>
      </div>
    );
  }

  if (kind === "stale") {
    const copy = dataStateCopy("stale", subject);

    return (
      <div className="data-state data-state--stale">
        <Alert
          action={action ? <RecoveryButton action={action} fallbackLabel={copy.action} /> : undefined}
          showIcon
          title={copy.title}
          type="warning"
        />
      </div>
    );
  }

  return (
    <div className="data-state data-state--error">
      <Alert
        action={action ? <RecoveryButton action={action} /> : undefined}
        showIcon
        title="读取失败"
        type="error"
      />
    </div>
  );
}

function RecoveryButton({ action, fallbackLabel = "重试" }: { action: RecoveryAction; fallbackLabel?: string }) {
  return (
    <Button onClick={action.onClick} size="small">
      {action.label ?? fallbackLabel}
    </Button>
  );
}

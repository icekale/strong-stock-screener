"use client";

import { Typography } from "antd";
import type { ReactNode } from "react";
import {
  buildWorkbenchContentClassName,
  buildWorkbenchPageClassName,
  joinClassNames,
} from "./workbenchLayout";

type WorkbenchPageProps = {
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  description?: ReactNode;
  eyebrow?: ReactNode;
  meta?: ReactNode;
  status?: ReactNode;
  title?: ReactNode;
};

export function WorkbenchPage({
  actions,
  children,
  className,
  contentClassName,
  description,
  eyebrow,
  meta,
  status,
  title,
}: WorkbenchPageProps) {
  return (
    <main className={buildWorkbenchPageClassName(className)}>
      <div className={buildWorkbenchContentClassName(contentClassName)}>
        {title || description || eyebrow || actions || status || meta ? (
          <WorkbenchPageHeader
            actions={actions}
            description={description}
            eyebrow={eyebrow}
            meta={meta}
            status={status}
            title={title}
          />
        ) : null}
        {children}
      </div>
    </main>
  );
}

function WorkbenchPageHeader({
  actions,
  description,
  eyebrow,
  meta,
  status,
  title,
}: Omit<WorkbenchPageProps, "children" | "className" | "contentClassName">) {
  return (
    <section className="workbench-page-header workbench-panel rounded-xl border px-4 py-3">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0">
          {eyebrow ? (
            <Typography.Text className="workbench-muted text-xs font-semibold">
              {eyebrow}
            </Typography.Text>
          ) : null}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {title ? (
              <Typography.Title className="workbench-page-title m-0 text-[#11100e]" level={3}>
                {title}
              </Typography.Title>
            ) : null}
            {status}
          </div>
          {description ? (
            <Typography.Text className="workbench-muted mt-1 block text-sm">
              {description}
            </Typography.Text>
          ) : null}
          {meta ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#7b756d]">
              {meta}
            </div>
          ) : null}
        </div>
        {actions ? (
          <div className={joinClassNames("flex flex-wrap items-center gap-2", "lg:justify-end")}>
            {actions}
          </div>
        ) : null}
      </div>
    </section>
  );
}

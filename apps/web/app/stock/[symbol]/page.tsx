"use client";

import { Skeleton } from "antd";
import dynamic from "next/dynamic";
import { use, type ComponentType } from "react";
import "kline-charts-react/style.css";
import { PageFrame } from "../../../components/workbench/PageFrame";
import type { StockKlineWorkspaceProps } from "./types";

const StockKlineWorkspace = dynamic(
  () => import("./StockKlineWorkspace").then((module) => module.StockKlineWorkspace),
  { ssr: false, loading: () => <StockKlineWorkspacePlaceholder /> },
) as ComponentType<StockKlineWorkspaceProps>;

export default function StockKlinePage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = use(params);
  const symbol = decodeURIComponent(rawSymbol);
  return <StockKlineWorkspace symbol={symbol} />;
}

function StockKlineWorkspacePlaceholder() {
  return (
    <PageFrame context="正在加载个股行情、K 线和研究数据。" contentVariant="flush" title="个股 K 线">
      <section aria-busy="true" aria-label="正在加载个股 K 线" className="grid min-h-screen lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="hidden min-h-screen border-r border-[var(--app-border)] bg-[var(--app-surface)] lg:block">
          <div className="sticky top-0 flex h-screen flex-col p-4">
            <Skeleton active paragraph={{ rows: 12 }} title={false} />
          </div>
        </aside>
        <section className="min-w-0">
          <header className="border-b border-[var(--app-border)] bg-[var(--app-surface)] px-4 py-4" />
          <div className="p-4">
            <section className="compact-panel p-4">
              <Skeleton active paragraph={{ rows: 12 }} />
            </section>
          </div>
        </section>
      </section>
    </PageFrame>
  );
}

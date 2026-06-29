"use client";

import { Card, Skeleton, Typography } from "antd";
import dynamic from "next/dynamic";
import { use, type ComponentType } from "react";
import "kline-charts-react/style.css";
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
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="hidden min-h-screen border-r border-slate-200 bg-white lg:block">
          <div className="sticky top-0 flex h-screen flex-col p-4">
            <Skeleton active paragraph={{ rows: 12 }} title={false} />
          </div>
        </aside>
        <section className="min-w-0">
          <header className="border-b border-slate-200 bg-white px-4 py-4">
            <Typography.Text className="text-xs font-semibold uppercase text-slate-400">Stock Detail</Typography.Text>
            <Typography.Title className="mt-1 text-xl font-black text-slate-950" level={1}>
              个股 K 线
            </Typography.Title>
          </header>
          <div className="p-4">
            <Card className="workbench-card">
              <Skeleton active paragraph={{ rows: 12 }} />
            </Card>
          </div>
        </section>
      </div>
    </main>
  );
}

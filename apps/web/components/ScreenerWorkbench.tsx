"use client";

import { Alert, App } from "antd";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { SyntheticEvent } from "react";
import type {
  DataSourceStatusResponse,
  MarketOverviewResponse,
  ScreenRunFilters,
  ScreenRunJobState,
  ScreenStrategy,
  SectorRadarResponse,
  SentimentSummaryResponse,
  StrongStockIntradaySnapshot,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistPoolItem,
} from "../lib/types";
import { FilterLogicRail } from "./screener/FilterLogicRail";
import { MarketOverviewPanels, SectorFlowHeatmapPanel, SectorStrengthPanel } from "./screener/MarketOverviewPanels";
import { buildMarketDashboardStats, sourceSummary } from "./screener/screenerUtils";
import { PageFrame } from "./workbench/PageFrame";

const CandidateResults = dynamic(
  () => import("./screener/CandidateResults").then((module) => module.CandidateResults),
  {
    ssr: false,
    loading: () => <ScreenerResultsPlaceholder loading />,
  },
);

type ScreenerWorkbenchProps = {
  tradeDate: string;
  sources: DataSourceStatusResponse | null;
  result: StrongStockScreeningResponse | null;
  intraday: StrongStockIntradaySnapshot | null;
  marketOverview: MarketOverviewResponse | null;
  marketSupportLoading: boolean;
  sectorRadar: SectorRadarResponse | null;
  sentimentSummary: SentimentSummaryResponse | null;
  running: boolean;
  screenJob: ScreenRunJobState | null;
  watchlistPoolItems: WatchlistPoolItem[];
  watchlistMessage: string | null;
  strategy: ScreenStrategy;
  scanLimit: number;
  screenFilters: ScreenRunFilters;
  screenFiltersSaved: boolean;
  error: string | null;
  onScanLimitChange: (value: number) => void;
  onScreenFiltersChange: (value: ScreenRunFilters) => void;
  onSaveScreenFilters: () => void;
  onStrategyChange: (value: ScreenStrategy) => void;
  onTradeDateChange: (value: string) => void;
  onAddToWatchlist: (item: StrongStockScreeningItem, group: string, tags: string[]) => void;
  onAddManyToWatchlist: (items: StrongStockScreeningItem[], group: string, tags: string[]) => void;
  onRun: () => void;
  onLoadMarketSupport: () => void;
  onRefreshSources: () => void;
};

export function ScreenerWorkbench({
  tradeDate,
  sources,
  result,
  marketOverview,
  marketSupportLoading,
  sectorRadar,
  sentimentSummary,
  running,
  screenJob,
  watchlistPoolItems,
  watchlistMessage,
  strategy,
  scanLimit,
  screenFilters,
  screenFiltersSaved,
  error,
  onScanLimitChange,
  onScreenFiltersChange,
  onSaveScreenFilters,
  onStrategyChange,
  onTradeDateChange,
  onAddToWatchlist,
  onAddManyToWatchlist,
  onRun,
  onLoadMarketSupport,
  onRefreshSources,
}: ScreenerWorkbenchProps) {
  const candidates = result?.items ?? [];
  const { message } = App.useApp();
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  useEffect(() => {
    if (candidates.length === 0) {
      setSelectedSymbol(null);
      return;
    }
    if (!selectedSymbol || !candidates.some((item) => item.symbol === selectedSymbol)) {
      setSelectedSymbol(candidates[0].symbol);
    }
  }, [result, selectedSymbol, candidates]);

  const selectedItem = candidates.find((item) => item.symbol === selectedSymbol) ?? candidates[0] ?? null;
  const dashboardStats = useMemo(() => buildMarketDashboardStats(candidates, result), [candidates, result]);

  useEffect(() => {
    if (watchlistMessage) {
      void message.success(watchlistMessage);
    }
  }, [message, watchlistMessage]);

  return (
    <PageFrame
      contentClassName="p-0"
      context={`交易日 ${tradeDate} · 数据源 ${sourceSummary(sources).label}`}
      status={
        <span className="rounded-full border border-[var(--app-border)] px-2 py-0.5 text-xs font-medium text-[var(--app-muted)]">
          {screenJob?.message ?? (running ? "筛选中" : "待运行")}
        </span>
      }
      title="强势选股"
    >
      <div className="flex flex-col gap-0 px-5 pt-4">
        <MarketOverviewPanels
          candidates={candidates}
          generatedAt={marketOverview?.generated_at ?? result?.generated_at ?? null}
          marketOverview={marketOverview}
          onRun={onRun}
          result={result}
          running={running}
          sectorRadar={sectorRadar}
          sentimentSummary={sentimentSummary}
          sources={sources}
          stats={dashboardStats}
        />

        <FilterLogicRail
          filters={screenFilters}
          onRefreshSources={onRefreshSources}
          onRun={onRun}
          onScanLimitChange={onScanLimitChange}
          onScreenFiltersChange={onScreenFiltersChange}
          onSaveScreenFilters={onSaveScreenFilters}
          onStrategyChange={onStrategyChange}
          onTradeDateChange={onTradeDateChange}
          running={running}
          scanLimit={scanLimit}
          screenJob={screenJob}
          screenFiltersSaved={screenFiltersSaved}
          sources={sources}
          strategy={strategy}
          tradeDate={tradeDate}
          visibleCount={candidates.length}
        />

        {error && <Alert className="mt-4" showIcon title={error} type="error" />}

        {result || running ? (
          <CandidateResults
            generatedAt={result?.generated_at ?? null}
            items={candidates}
            onAddManyToWatchlist={onAddManyToWatchlist}
            onAddToWatchlist={onAddToWatchlist}
            onSelect={setSelectedSymbol}
            running={running}
            selectedSymbol={selectedItem?.symbol ?? null}
            watchlistMessage={watchlistMessage}
            watchlistPoolItems={watchlistPoolItems}
          />
        ) : (
          <ScreenerResultsPlaceholder />
        )}

        <HomepageMarketSupportPanel
          marketSupportLoading={marketSupportLoading}
          onLoadMarketSupport={onLoadMarketSupport}
          sectorRadar={sectorRadar}
        />

        <HomepageModelMaintenancePanel />
      </div>

      <div className="border-t border-[var(--app-border)] bg-[var(--app-raised)] px-5 py-3 text-xs text-[var(--app-muted)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="font-black text-[var(--app-ink)]">StockMaster · A股选股工作台</span>
          <span>Data: TickFlow / iFinD / 东方财富 · Delayed 15min · 仅作规则辅助，不构成投资建议</span>
        </div>
      </div>
    </PageFrame>
  );
}

function HomepageMarketSupportPanel({
  marketSupportLoading,
  onLoadMarketSupport,
  sectorRadar,
}: {
  marketSupportLoading: boolean;
  onLoadMarketSupport: () => void;
  sectorRadar: SectorRadarResponse | null;
}) {
  const [marketSupportOpen, setMarketSupportOpen] = useState(false);

  function handleToggle(event: SyntheticEvent<HTMLDetailsElement>) {
    const isOpen = event.currentTarget.open;
    setMarketSupportOpen(isOpen);
    if (isOpen) {
      onLoadMarketSupport();
    }
  }

  return (
    <section className="mt-4">
      <details className="rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)]" onToggle={handleToggle}>
        <summary className="cursor-pointer list-none px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-base font-black text-[var(--app-ink)]">市场辅助</h2>
              <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">
                板块资金流和强度只作为选股后的辅助确认，完整板块工作台仍在独立页面。
              </p>
            </div>
            <span className="rounded-full border border-[var(--app-border)] bg-white px-3 py-1 text-xs font-bold text-[var(--app-muted)]">
              {marketSupportLoading ? "正在加载" : marketSupportOpen ? "收起辅助" : "展开查看"}
            </span>
          </div>
        </summary>
        <div className="border-t border-[var(--app-border)] px-4 pb-4">
          {marketSupportOpen ? (
            <div className="mt-4 grid items-stretch gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
              <SectorFlowHeatmapPanel sectorRadar={sectorRadar} />
              <SectorStrengthPanel />
            </div>
          ) : (
            <p className="mt-4 text-sm font-medium text-[var(--app-muted)]">展开后加载板块资金流辅助数据。</p>
          )}
        </div>
      </details>
    </section>
  );
}

function HomepageModelMaintenancePanel() {
  return (
    <section className="mt-4">
      <div className="rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)] px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-black text-[var(--app-ink)]">AI 模型维护</h2>
            <p className="mt-1 text-xs font-medium text-[var(--app-muted)]">
              复盘样本、校准结果和数据源状态集中到独立页面，由 AI 生成待确认维护建议。
            </p>
          </div>
          <Link
            className="inline-flex items-center justify-center rounded-md border border-[var(--app-ink)] bg-[var(--app-ink)] px-3 py-2 text-xs font-black text-white no-underline hover:opacity-90"
            href="/model-maintenance"
          >
            查看模型维护
          </Link>
        </div>
      </div>
    </section>
  );
}

function ScreenerResultsPlaceholder({ loading = false }: { loading?: boolean }) {
  return (
    <section className="mt-4 rounded-xl border border-[var(--app-border)] bg-[var(--app-raised)] px-5 py-8 text-center">
      <h2 className="text-base font-black text-[var(--app-ink)]">选股结果 · Screener Results</h2>
      <p className="mt-2 text-sm font-medium text-[var(--app-muted)]">
        {loading ? "正在加载候选结果组件..." : "运行筛选后显示候选股票。"}
      </p>
    </section>
  );
}

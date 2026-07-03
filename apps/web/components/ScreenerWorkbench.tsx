"use client";

import { Alert, App } from "antd";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import type {
  BackgroundJobState,
  DataSourceStatusResponse,
  GsgfModelHealth,
  GsgfRealCalibrationSummary,
  GsgfReviewSummary,
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
import { GsgfFunnelPanel } from "./screener/GsgfFunnelPanel";
import type { GsgfCalibrationPanelProps, GsgfReviewPanelProps } from "./screener/GsgfWorkflowPanels";
import { MarketOverviewPanels, SectorFlowHeatmapPanel, SectorStrengthPanel } from "./screener/MarketOverviewPanels";
import { buildMarketDashboardStats } from "./screener/screenerUtils";

const CandidateResults = dynamic(
  () => import("./screener/CandidateResults").then((module) => module.CandidateResults),
  {
    ssr: false,
    loading: () => <ScreenerResultsPlaceholder loading />,
  },
);

const GsgfReviewPanel = dynamic(
  () => import("./screener/GsgfWorkflowPanels").then((module) => module.GsgfReviewPanel),
  { ssr: false },
);

const GsgfCalibrationPanel = dynamic(
  () => import("./screener/GsgfWorkflowPanels").then((module) => module.GsgfCalibrationPanel),
  { ssr: false },
);

type ScreenerWorkbenchProps = {
  tradeDate: string;
  sources: DataSourceStatusResponse | null;
  result: StrongStockScreeningResponse | null;
  intraday: StrongStockIntradaySnapshot | null;
  marketOverview: MarketOverviewResponse | null;
  sectorRadar: SectorRadarResponse | null;
  sentimentSummary: SentimentSummaryResponse | null;
  reviewSummary: GsgfReviewSummary | null;
  calibrationSummary: GsgfRealCalibrationSummary | null;
  calibrationJob: BackgroundJobState | null;
  gsgfHealth: GsgfModelHealth | null;
  running: boolean;
  screenJob: ScreenRunJobState | null;
  reviewRunning: boolean;
  calibrationRunning: boolean;
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
  onRunGsgfCalibration: (options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) => void;
  onCancelGsgfCalibration: () => void;
  onRecheckGsgfReview: () => void;
  onRefreshSources: () => void;
  onSaveGsgfReviewSnapshot: () => void;
};

export function ScreenerWorkbench({
  tradeDate,
  sources,
  result,
  marketOverview,
  sectorRadar,
  sentimentSummary,
  reviewSummary,
  calibrationSummary,
  calibrationJob,
  gsgfHealth,
  running,
  screenJob,
  reviewRunning,
  calibrationRunning,
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
  onRunGsgfCalibration,
  onCancelGsgfCalibration,
  onRecheckGsgfReview,
  onRefreshSources,
  onSaveGsgfReviewSnapshot,
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
    <main className="min-h-screen bg-[#f5f3f0] text-[#11100e]">
      <div className="mx-auto max-w-none px-5 py-4">
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

        <div className="mt-4 grid items-stretch gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
          <SectorFlowHeatmapPanel sectorRadar={sectorRadar} />
          <SectorStrengthPanel />
        </div>

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

        <GsgfReviewPanel
          gsgfHealth={gsgfHealth}
          onRecheck={onRecheckGsgfReview}
          onSaveSnapshot={onSaveGsgfReviewSnapshot}
          reviewRunning={reviewRunning}
          reviewSummary={reviewSummary}
        />

        <GsgfCalibrationPanel
          calibrationJob={calibrationJob}
          calibrationRunning={calibrationRunning}
          calibrationSummary={calibrationSummary}
          defaultTradeDate={tradeDate}
          onCancelCalibration={onCancelGsgfCalibration}
          onRunCalibration={onRunGsgfCalibration}
        />

        <GsgfFunnelPanel
          onAddToWatchlist={onAddToWatchlist}
          result={result}
          running={running}
          watchlistPoolItems={watchlistPoolItems}
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
      </div>

      <div className="border-t border-[#ddd8d0] bg-[#f5f3f0] px-5 py-3 text-xs text-[#7b756d]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="font-black text-[#11100e]">StockMaster · A股选股工作台</span>
          <span>Data: TickFlow / iFinD / 东方财富 · Delayed 15min · 仅作规则辅助，不构成投资建议</span>
        </div>
      </div>
    </main>
  );
}

function ScreenerResultsPlaceholder({ loading = false }: { loading?: boolean }) {
  return (
    <section className="mt-4 rounded-xl border border-[#ddd8d0] bg-[#f8f7f4] px-5 py-8 text-center">
      <h2 className="text-base font-black text-[#11100e]">选股结果 · Screener Results</h2>
      <p className="mt-2 text-sm font-medium text-[#7b756d]">
        {loading ? "正在加载候选结果组件..." : "运行筛选后显示候选股票。"}
      </p>
    </section>
  );
}

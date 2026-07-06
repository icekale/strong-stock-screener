"use client";

import { ExperimentOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Button, Collapse, Empty, Input, InputNumber, Progress, Segmented, Select, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addWatchlistPoolItem,
  createAuctionSnapshotJob,
  finalizeAuctionReview,
  getAuctionLatest,
  getAuctionModelLiveConfirmation,
  getAuctionModelTop3,
  getAuctionReview,
  getAuctionReviewLatest,
  getAuctionRuleSummary,
  getAuctionSnapshotJob,
  getAuctionTimeline,
} from "../../lib/api";
import { selectAuctionFocusIndustryItems, selectAuctionHotIndustryItems } from "../../lib/auctionIndustryFilters";
import {
  auctionModelBucketLabel,
  auctionModelCacheStatusLabel,
  auctionModelLiveConfirmationColor,
  auctionModelLiveConfirmationLabel,
  auctionModelRunStatusText,
  selectAuctionModelPreviewItems,
} from "../../lib/auctionModel";
import { selectAuctionMainlineTopItems, selectAuctionRiskFocusItems } from "../../lib/auctionPanelLimits";
import {
  AUCTION_SORT_OPTIONS,
  getAuctionLiquidityWarning,
  getAuctionSortDescription,
  sortAuctionItems,
  type AuctionSortMode,
} from "../../lib/auctionSort";
import { buildAuctionClosePctBySymbol } from "../../lib/auctionReviewMetrics";
import { loadAuctionReviewSummaryForDate } from "../../lib/auctionReviewLoader";
import { buildStockDetailHref } from "../../lib/stockNavigation";
import type {
  AuctionReviewRecord,
  AuctionReviewSummary,
  AuctionRuleBucket,
  AuctionModelPredictionItem,
  AuctionModelTop3Response,
  AuctionTop3LiveConfirmationItem,
  AuctionTop3LiveConfirmationResponse,
  AuctionSnapshotItem,
  AuctionSnapshotResponse,
  AuctionTimelineResponse,
  BackgroundJobState,
} from "../../lib/types";

type AuctionTierFilter = "all" | AuctionSnapshotItem["tier"];
type AuctionModelLoadingMode = "cache" | "refresh";
type IndustryAuctionStat = {
  avgOpenGapPct: number | null;
  count: number;
  industry: string;
  strongCount: number;
  turnoverCny: number;
};

const TIER_FILTERS: Array<{ label: string; value: AuctionTierFilter }> = [
  { label: "全部", value: "all" },
  { label: "强势高开", value: "strong_high_open" },
  { label: "放量活跃", value: "volume_leader" },
  { label: "高开过热", value: "risk_overheat" },
  { label: "低开观察", value: "reversal_watch" },
  { label: "低开偏弱", value: "weak_low_open" },
];

export function AuctionWorkspace() {
  const { message } = App.useApp();
  const [data, setData] = useState<AuctionSnapshotResponse | null>(null);
  const [timeline, setTimeline] = useState<AuctionTimelineResponse | null>(null);
  const [reviewSummary, setReviewSummary] = useState<AuctionReviewSummary | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewFinalizing, setReviewFinalizing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshJob, setRefreshJob] = useState<BackgroundJobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<AuctionTierFilter>("all");
  const [industryFilter, setIndustryFilter] = useState<string>("all");
  const [auctionSortMode, setAuctionSortMode] = useState<AuctionSortMode>("score");
  const [highOpenRiskThreshold, setHighOpenRiskThreshold] = useState(7);
  const [watchlistSavingSymbol, setWatchlistSavingSymbol] = useState<string | null>(null);
  const [modelTradeDate, setModelTradeDate] = useState(() => nextWeekdayDate());
  const [modelRun, setModelRun] = useState<AuctionModelTop3Response | null>(null);
  const [modelLiveConfirmation, setModelLiveConfirmation] = useState<AuctionTop3LiveConfirmationResponse | null>(null);
  const [modelLiveError, setModelLiveError] = useState<string | null>(null);
  const [modelLoadingMode, setModelLoadingMode] = useState<AuctionModelLoadingMode | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSavingSymbol, setModelSavingSymbol] = useState<string | null>(null);
  const refreshPromiseRef = useRef<Promise<void> | null>(null);
  const reviewRequestRef = useRef(0);

  const loadTimeline = useCallback(async () => {
    try {
      const snapshotTimeline = await getAuctionTimeline(5);
      setTimeline(snapshotTimeline);
    } catch {
      setTimeline(null);
    }
  }, []);

  const loadReview = useCallback(async (tradeDate?: string | null) => {
    const requestId = reviewRequestRef.current + 1;
    reviewRequestRef.current = requestId;
    setReviewLoading(true);
    try {
      const summary = await loadAuctionReviewSummaryForDate(tradeDate, {
        getAuctionReview,
        getAuctionReviewLatest,
        getAuctionRuleSummary,
      });
      if (reviewRequestRef.current === requestId) {
        setReviewSummary(summary);
      }
    } finally {
      if (reviewRequestRef.current === requestId) {
        setReviewLoading(false);
      }
    }
  }, []);

  const loadLatest = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      const snapshot = await getAuctionLatest(100);
      setData(snapshot);
      setError(null);
      return snapshot;
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取竞价雷达快照失败");
      return null;
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, []);

  const refresh = useCallback(async (showSuccess = true) => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }
    setRefreshing(true);
    setError(null);
    const promise = (async () => {
      try {
        let job = await createAuctionSnapshotJob(100);
        setRefreshJob(job);
        while (job.status === "pending" || job.status === "running") {
          await sleep(1200);
          job = await getAuctionSnapshotJob(job.job_id);
          setRefreshJob(job);
        }
        if (job.status !== "success") {
          throw new Error(job.error || job.message || "竞价刷新失败");
        }
        await Promise.all([loadLatest(false), loadTimeline()]);
        if (showSuccess) {
          void message.success("竞价刷新完成");
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "读取竞价雷达失败";
        setError(errorMessage);
        void message.error(errorMessage);
      } finally {
        setRefreshing(false);
        refreshPromiseRef.current = null;
      }
    })();
    refreshPromiseRef.current = promise;
    return promise;
  }, [loadLatest, loadTimeline, message]);

  useEffect(() => {
    void loadLatest(true).then((snapshot) => {
      if (!snapshot || snapshot.snapshot_status === "missing") {
        void refresh(false);
      }
    });
    void loadTimeline();
    const timer = window.setInterval(() => {
      void loadLatest(false);
      void loadTimeline();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadLatest, loadTimeline, refresh]);

  useEffect(() => {
    if (loading && !data?.trade_date) {
      return;
    }
    void loadReview(data?.trade_date);
  }, [data?.trade_date, loadReview, loading]);

  useEffect(() => {
    let active = true;
    void (async () => {
      setModelLiveConfirmation(null);
      setModelLiveError(null);
      try {
        const cached = await getAuctionModelTop3(modelTradeDate, { cacheOnly: true });
        if (active) {
          setModelRun(cached);
          setModelError(null);
        }
        try {
          const liveConfirmation = await getAuctionModelLiveConfirmation(cached.trade_date);
          if (active) {
            setModelLiveConfirmation(liveConfirmation);
            setModelLiveError(null);
          }
        } catch (err) {
          if (active) {
            setModelLiveError(err instanceof Error ? err.message : "读取竞价模型Top3实盘确认失败");
          }
        }
      } catch {
        if (active) {
          setModelRun(null);
          setModelLiveConfirmation(null);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [modelTradeDate]);

  const loadAuctionModelLiveConfirmation = useCallback(async (tradeDate: string) => {
    try {
      const liveConfirmation = await getAuctionModelLiveConfirmation(tradeDate);
      setModelLiveConfirmation(liveConfirmation);
      setModelLiveError(null);
      return liveConfirmation;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "读取竞价模型Top3实盘确认失败";
      setModelLiveConfirmation(null);
      setModelLiveError(errorMessage);
      return null;
    }
  }, []);

  const observationItems = useMemo(
    () =>
      (data?.items ?? [])
        .filter(
          (item) =>
            item.risk_flags.length > 0 ||
            item.tier === "reversal_watch" ||
            (item.open_gap_pct ?? 0) >= highOpenRiskThreshold,
        )
        .slice(0, 12),
    [data, highOpenRiskThreshold],
  );
  const visibleItems = useMemo(
    () =>
      sortAuctionItems(
        (data?.items ?? []).filter(
          (item) =>
            (tierFilter === "all" || item.tier === tierFilter) &&
            (industryFilter === "all" || (item.industry || "未标注") === industryFilter),
        ),
        auctionSortMode,
      ),
    [auctionSortMode, data, industryFilter, tierFilter],
  );
  const industryStats = useMemo(() => buildIndustryStats(data?.items ?? []), [data]);
  const concentration = useMemo(() => buildIndustryConcentration(industryStats, data?.items.length ?? 0), [data, industryStats]);
  const closePctBySymbol = useMemo(
    () => buildAuctionClosePctBySymbol(reviewSummary?.records ?? [], data?.trade_date),
    [data?.trade_date, reviewSummary?.records],
  );

  async function handleAddToWatchlist(item: AuctionSnapshotItem) {
    setWatchlistSavingSymbol(item.symbol);
    setError(null);
    try {
      await addWatchlistPoolItem({
        symbol: item.symbol,
        name: item.name,
        industry: item.industry,
        group: "竞价雷达",
        tags: ["竞价", item.industry || "未标注", tierLabel(item.tier)],
        note: buildAuctionWatchlistNote(item),
      });
      void message.success(`已加入自选：${item.name || item.symbol}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入自选股失败");
    } finally {
      setWatchlistSavingSymbol(null);
    }
  }

  async function handleLoadCachedAuctionModel() {
    setModelLoadingMode("cache");
    setModelError(null);
    setModelLiveConfirmation(null);
    setModelLiveError(null);
    try {
      const run = await getAuctionModelTop3(modelTradeDate, { cacheOnly: true });
      setModelRun(run);
      void loadAuctionModelLiveConfirmation(run.trade_date);
      void message.success(`已读取竞价模型Top3缓存：${run.trade_date}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "读取竞价模型Top3缓存失败";
      setModelError(errorMessage);
      void message.warning(errorMessage);
    } finally {
      setModelLoadingMode(null);
    }
  }

  async function handleRefreshAuctionModel() {
    setModelLoadingMode("refresh");
    setModelError(null);
    setModelLiveConfirmation(null);
    setModelLiveError(null);
    try {
      const run = await getAuctionModelTop3(modelTradeDate, { refresh: true });
      setModelRun(run);
      void loadAuctionModelLiveConfirmation(run.trade_date);
      void message.success(`竞价模型Top3已重新生成：${run.trade_date}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "重新生成竞价模型Top3失败";
      setModelError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setModelLoadingMode(null);
    }
  }

  async function handleAddModelToWatchlist(item: AuctionModelPredictionItem) {
    setModelSavingSymbol(item.symbol);
    setError(null);
    try {
      await addWatchlistPoolItem({
        symbol: item.symbol,
        name: item.name,
        industry: null,
        group: "竞价模型Top3",
        tags: ["竞价模型", auctionModelBucketLabel(item.bucket), item.feature_end_date || "日K特征"],
        note: buildAuctionModelWatchlistNote(item, modelRun),
      });
      void message.success(`已加入自选：${item.name || item.symbol}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入自选股失败");
    } finally {
      setModelSavingSymbol(null);
    }
  }

  async function handleFinalizeReview() {
    const tradeDate = data?.trade_date || todayDate();
    setReviewFinalizing(true);
    try {
      const summary = await finalizeAuctionReview(tradeDate);
      setReviewSummary(summary);
      void message.success(`竞价复盘已生成：${tradeDate}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "生成竞价复盘失败";
      setError(errorMessage);
      void message.error(errorMessage);
    } finally {
      setReviewFinalizing(false);
    }
  }

  return (
    <main className="workbench-page min-h-screen p-3 lg:p-5">
      <section className="auction-status-strip auction-command-strip workbench-panel mb-4 rounded-xl border px-4 py-3">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(220px,auto)] xl:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Typography.Title className="m-0 text-[#11100e]" level={3}>
                竞价雷达
              </Typography.Title>
              <Tag color={sessionColor(data?.session)}>{sessionLabel(data?.session)}</Tag>
              <Tag color={snapshotStatusColor(data?.snapshot_status)}>{snapshotStatusLabel(data?.snapshot_status)}</Tag>
              <Tag color="red">早盘作战台</Tag>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-semibold text-[#7b756d]">
              <span>{data?.trade_date ?? "等待数据"}</span>
              <span>缓存年龄 {formatCacheAge(data?.cache_age_seconds)}</span>
              <span>自动快照 · TickFlow 全A实时行情 · 09:25 锁定主榜</span>
              <span>{concentration.message}</span>
            </div>
          </div>
          <div className="flex min-w-[180px] flex-col items-stretch gap-2 sm:items-end">
            <Button icon={<ReloadOutlined />} loading={refreshing} onClick={() => void refresh()} type="primary">
              刷新竞价
            </Button>
            {refreshJob && refreshing && (
              <div className="w-full max-w-[260px] rounded-lg border border-[#eee7db] bg-white px-3 py-2 text-xs text-[#7b756d]">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="truncate font-semibold">{refreshJob.message || "竞价刷新运行中"}</span>
                  <span className="shrink-0 font-black text-[#d92d20]">
                    {refreshJob.progress_current}/{refreshJob.progress_total || 1}
                  </span>
                </div>
                <Progress
                  percent={jobProgressPercent(refreshJob)}
                  showInfo={false}
                  size="small"
                  status={refreshJob.status === "failed" ? "exception" : "active"}
                  strokeColor="#d92d20"
                />
              </div>
            )}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 xl:grid-cols-4">
          <MetricCard compact label="竞价候选" value={data?.metrics.candidate_count ?? null} suffix="只" />
          <MetricCard compact label="强势高开" value={data?.metrics.strong_high_open_count ?? null} suffix="只" tone="red" />
          <MetricCard compact label="高开风险" value={data?.metrics.high_risk_count ?? null} suffix="只" tone="amber" />
          <MetricCard compact label="候选成交额" value={data?.metrics.total_turnover_cny ?? null} formatter={formatCny} />
        </div>
        <AuctionTrustStrip data={data} />
        <AuctionModelTrialPanel
          error={modelError}
          liveConfirmation={modelLiveConfirmation}
          liveConfirmationError={modelLiveError}
          loadingMode={modelLoadingMode}
          onAddToWatchlist={handleAddModelToWatchlist}
          onLoadCached={handleLoadCachedAuctionModel}
          onRefresh={handleRefreshAuctionModel}
          onTradeDateChange={setModelTradeDate}
          run={modelRun}
          savingSymbol={modelSavingSymbol}
          tradeDate={modelTradeDate}
        />
      </section>

      {error && <Alert className="mb-4" showIcon title={error} type="error" />}

      <section className="auction-primary-grid grid gap-4 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="min-w-0 space-y-3">
          <AuctionTimelinePanel timeline={timeline} />

          <section className="workbench-panel overflow-hidden rounded-xl border">
            <div className="workbench-panel-divider flex flex-col gap-3 border-b px-4 py-3 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="text-sm font-black text-[#11100e]">竞价强度榜</div>
                <div className="text-xs text-[#7b756d]">
                  当前显示 {visibleItems.length}/{data?.items.length ?? 0} 只，09:25 后主榜不再被盘中行情覆盖，{getAuctionSortDescription(auctionSortMode)}
                </div>
              </div>
              <Tag color="red">第一屏主视野</Tag>
            </div>
            <AuctionControlBar
              activeIndustry={industryFilter}
              auctionSortMode={auctionSortMode}
              concentrationMessage={concentration.message}
              highOpenRiskThreshold={highOpenRiskThreshold}
              industryStats={industryStats}
              onHighOpenRiskThresholdChange={setHighOpenRiskThreshold}
              onSelectAuctionSortMode={setAuctionSortMode}
              onSelectIndustry={setIndustryFilter}
              onSelectTier={setTierFilter}
              tierFilter={tierFilter}
              totalCount={data?.items.length ?? 0}
            />
            <div className="p-2 lg:p-4">
              <AuctionTable
                closePctBySymbol={closePctBySymbol}
                items={visibleItems}
                loading={loading && !data}
                onAddToWatchlist={handleAddToWatchlist}
                savingSymbol={watchlistSavingSymbol}
              />
            </div>
          </section>

          <AuctionReviewPanel
            finalizing={reviewFinalizing}
            loading={reviewLoading}
            onFinalize={handleFinalizeReview}
            summary={reviewSummary}
          />
        </section>

        <aside className="auction-side-rail space-y-3 2xl:sticky 2xl:top-4 2xl:self-start">
          <MainlineTopPanel
            activeIndustry={industryFilter}
            industryStats={industryStats}
            loading={loading && !data}
            onSelectIndustry={setIndustryFilter}
            totalCount={data?.items.length ?? 0}
          />
          <RiskFocusPanel
            highOpenRiskThreshold={highOpenRiskThreshold}
            items={observationItems}
            loading={loading && !data}
          />
          <section className="workbench-panel rounded-xl border">
            <Collapse
              bordered={false}
              className="bg-transparent"
              items={[
                {
                  key: "source",
                  label: (
                    <div>
                      <div className="text-sm font-black text-[#11100e]">数据源状态</div>
                      <div className="text-xs text-[#7b756d]">默认收起，避免早盘盯盘时占主视野。</div>
                    </div>
                  ),
                  children: (
                    <div className="space-y-2">
                      {(data?.source_status ?? []).length ? (
                        (data?.source_status ?? []).map((item, index) => (
                          <div className="rounded-lg border border-[#e3ddd3] bg-white p-3 text-xs" key={`${item.source}-${index}`}>
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-black text-[#11100e]">{item.source}</span>
                              <Tag color={item.status === "success" ? "green" : "orange"}>{item.status}</Tag>
                            </div>
                            <div className="mt-1 leading-5 text-[#7b756d]">{item.detail}</div>
                          </div>
                        ))
                      ) : (
                        <Empty description="暂无数据源状态" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </section>
        </aside>
      </section>
    </main>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function AuctionModelTrialPanel({
  error,
  liveConfirmation,
  liveConfirmationError,
  loadingMode,
  onAddToWatchlist,
  onLoadCached,
  onRefresh,
  onTradeDateChange,
  run,
  savingSymbol,
  tradeDate,
}: {
  error: string | null;
  liveConfirmation: AuctionTop3LiveConfirmationResponse | null;
  liveConfirmationError: string | null;
  loadingMode: AuctionModelLoadingMode | null;
  onAddToWatchlist: (item: AuctionModelPredictionItem) => void;
  onLoadCached: () => void;
  onRefresh: () => void;
  onTradeDateChange: (value: string) => void;
  run: AuctionModelTop3Response | null;
  savingSymbol: string | null;
  tradeDate: string;
}) {
  const previewItems = useMemo(() => selectAuctionModelPreviewItems(run?.items ?? []), [run]);
  const liveConfirmationBySymbol = useMemo(() => {
    if (!liveConfirmation || liveConfirmation.trade_date !== run?.trade_date) {
      return new Map<string, AuctionTop3LiveConfirmationItem>();
    }
    return new Map(liveConfirmation.items.map((item) => [item.symbol, item]));
  }, [liveConfirmation, run?.trade_date]);
  const backtest = run?.backtest ?? null;
  const statusText =
    loadingMode === "refresh"
      ? "重新生成中 · 构建全市场120日特征"
      : loadingMode === "cache"
        ? "读取缓存中"
        : auctionModelRunStatusText(run);
  const shouldShowBody = Boolean(error || loadingMode || run);
  return (
    <section className="mt-2 overflow-hidden rounded-lg border border-[#e3ddd3] bg-white">
      <div className="flex flex-col gap-2 px-3 py-2.5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-black text-[#11100e]">模型 Top3 试运行</span>
            <Tag color="orange">研究信号 · 非自动交易</Tag>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#7b756d]">
            <span>{statusText}</span>
            <span>{run?.model_version ?? "free-stockdb 五年模型"}</span>
            {run ? <span>{auctionModelCacheStatusLabel(run.cache_status)} · 生成 {formatAuctionModelGeneratedAt(run.generated_at)}</span> : null}
            <span>{run?.guard_rule ?? "09:25确认，10:00守卫"}</span>
          </div>
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 xl:shrink-0">
          <Input
            className="min-w-0 xl:w-[160px]"
            onChange={(event) => onTradeDateChange(event.target.value)}
            size="small"
            type="date"
            value={tradeDate}
          />
          <Button
            className="whitespace-nowrap"
            disabled={!tradeDate || loadingMode === "refresh"}
            icon={<ReloadOutlined />}
            loading={loadingMode === "cache"}
            onClick={onLoadCached}
            size="small"
            type="primary"
          >
            读取缓存
          </Button>
          <Button
            className="whitespace-nowrap"
            disabled={!tradeDate || loadingMode === "cache"}
            icon={<ExperimentOutlined />}
            loading={loadingMode === "refresh"}
            onClick={onRefresh}
            size="small"
          >
            重新生成
          </Button>
        </div>
      </div>

      {shouldShowBody ? (
        <div className="min-w-0 border-t border-[#eee7db] px-3 py-2">
          {error ? <Alert className="mb-2" showIcon title={error} type="warning" /> : null}
          {liveConfirmationError ? <Alert className="mb-2" message={liveConfirmationError} showIcon type="warning" /> : null}
          {loadingMode ? (
            <div className="rounded-md border border-dashed border-[#e3ddd3] bg-[#faf7f1] px-3 py-2 text-xs font-semibold text-[#7b756d]">
              {loadingMode === "refresh" ? "正在构建全市场120日特征，通常需要约1-2分钟。" : "正在读取本地缓存结果。"}
            </div>
          ) : previewItems.length ? (
            <>
              {backtest ? (
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-md bg-[#faf7f1] px-2 py-1 text-[#7b756d]">
                    历史胜率 <b className="text-[#11100e]">{formatRatioPct(backtest.win_rate)}</b>
                  </span>
                  <span className="rounded-md bg-[#fff3f0] px-2 py-1 text-[#7b756d]">
                    赔率 <b className="text-[#d92d20]">{formatNumber(backtest.payoff_ratio)}</b>
                  </span>
                  <span className="rounded-md bg-[#fff3f0] px-2 py-1 text-[#7b756d]">
                    期望收益 <b className="text-[#d92d20]">{formatSignedRatioPct(backtest.expectancy)}</b>
                  </span>
                  <span className="rounded-md bg-[#faf7f1] px-2 py-1 text-[#7b756d]">
                    单账户回测 <b className="text-[#11100e]">{formatRawPct(backtest.capital_return_pct)}</b>
                  </span>
                </div>
              ) : null}
              <div className="grid gap-2 lg:grid-cols-3">
                {previewItems.map((item) => {
                  const liveItem = liveConfirmationBySymbol.get(item.symbol);
                  return (
                    <div className="rounded-lg border border-[#e3ddd3] bg-[#faf7f1] px-3 py-2" key={item.symbol}>
                      <div className="flex items-start justify-between gap-2">
                        <Link className="min-w-0 font-black text-[#11100e]" href={modelStockHref(item)}>
                          <span className="block truncate">{item.name || item.symbol}</span>
                          <span className="block text-xs font-semibold text-[#7b756d]">{item.symbol}</span>
                        </Link>
                        <Tag className="m-0 shrink-0" color={auctionModelBucketColor(item.bucket)}>
                          {auctionModelBucketLabel(item.bucket)}
                        </Tag>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
                        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">排名 #{item.rank ?? "--"}</span>
                        <span className="rounded-md bg-[#fff3f0] px-2 py-1 font-black text-[#d92d20]">
                          概率 {formatProbability(item.prob_3pct)}
                        </span>
                        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">前收 {formatPrice(item.prev_close_price)}</span>
                        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">
                          流通 {formatCny(item.market_cap_float)}
                        </span>
                        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">
                          3日均额 {formatCny(item.avg_amount_3d)}
                        </span>
                      </div>
                      {item.risk_flags.length ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {item.risk_flags.map((flag) => (
                            <Tag className="m-0" color="orange" key={flag}>
                              {flag}
                            </Tag>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-1 truncate text-xs leading-5 text-[#7b756d]">
                        {(item.trend_reasons.length ? item.trend_reasons : item.data_quality).join(" · ") || "--"}
                      </div>
                      {liveItem ? <AuctionModelLiveConfirmationBlock item={liveItem} /> : null}
                      <div className="mt-1 flex justify-end">
                        <Button
                          loading={savingSymbol === item.symbol}
                          onClick={() => onAddToWatchlist(item)}
                          size="small"
                          type="link"
                        >
                          加入自选
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="rounded-md border border-dashed border-[#e3ddd3] bg-[#faf7f1] px-3 py-2 text-xs text-[#7b756d]">
              暂无可展示候选，请确认训练数据和交易日。
            </div>
          )}
          {run?.source_status.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {run.source_status.map((item) => (
                <Tag color={item.status === "success" ? "green" : item.status === "stale" ? "orange" : "default"} key={item.source}>
                  {item.source}
                </Tag>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function AuctionModelLiveConfirmationBlock({ item }: { item: AuctionTop3LiveConfirmationItem }) {
  const realtime = item.realtime;
  const reasons = item.reasons.slice(0, 2);
  const risks = item.risk_flags.slice(0, 2);
  return (
    <div className="mt-2 border-t border-[#e3ddd3] pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-black text-[#11100e]">实盘确认</span>
        <Tag className="m-0" color={auctionModelLiveConfirmationColor(item.confirmation)}>
          {auctionModelLiveConfirmationLabel(item.confirmation)}
        </Tag>
      </div>
      <div className="mt-1 flex flex-wrap gap-1 text-xs">
        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">高开 {formatPct(realtime?.open_gap_pct ?? null)}</span>
        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">现涨 {formatPct(realtime?.current_pct_change ?? null)}</span>
        <span className="rounded-md bg-white px-2 py-1 text-[#7b756d]">竞额 {formatCny(realtime?.turnover_cny ?? null)}</span>
      </div>
      {reasons.length || risks.length ? (
        <div className="mt-1 flex flex-wrap gap-1">
          {reasons.map((reason) => (
            <Tag className="m-0" color="green" key={`reason-${reason}`}>
              {reason}
            </Tag>
          ))}
          {risks.map((risk) => (
            <Tag className="m-0" color="orange" key={`risk-${risk}`}>
              {risk}
            </Tag>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AuctionTrustStrip({ data }: { data: AuctionSnapshotResponse | null }) {
  const sourceStatus = data?.source_status ?? [];
  const failedCount = sourceStatus.filter((item) => item.status === "failed" || item.status === "missing_key").length;
  const staleCount = sourceStatus.filter((item) => item.status === "stale").length;
  const trustText =
    failedCount > 0
      ? "竞价可信度：降级"
      : data?.snapshot_status === "missing"
        ? "竞价可信度：等待快照"
        : staleCount > 0 || data?.snapshot_status === "stale"
          ? "竞价可信度：缓存/待刷新"
          : "竞价可信度：可用";
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-[#e3ddd3] bg-white px-3 py-2 text-xs">
      <span className="font-black text-[#7b756d]">数据可信度</span>
      <Tag className="m-0" color={snapshotStatusColor(data?.snapshot_status)}>
        {snapshotStatusLabel(data?.snapshot_status)}
      </Tag>
      <Tag className="m-0" color={failedCount > 0 ? "red" : staleCount > 0 ? "orange" : "green"}>
        {trustText}
      </Tag>
      <Tag className="m-0" color={sourceStatus.length ? "blue" : "default"}>
        数据源 {sourceStatus.length || "--"}
      </Tag>
      <span className="text-[#7b756d]">缓存年龄 {formatCacheAge(data?.cache_age_seconds)}</span>
    </div>
  );
}

function jobProgressPercent(job: BackgroundJobState): number {
  const total = Math.max(1, job.progress_total || 1);
  return Math.max(0, Math.min(100, Math.round((job.progress_current / total) * 100)));
}

function AuctionControlBar({
  activeIndustry,
  auctionSortMode,
  concentrationMessage,
  highOpenRiskThreshold,
  industryStats,
  onHighOpenRiskThresholdChange,
  onSelectAuctionSortMode,
  onSelectIndustry,
  onSelectTier,
  tierFilter,
  totalCount,
}: {
  activeIndustry: string;
  auctionSortMode: AuctionSortMode;
  concentrationMessage: string;
  highOpenRiskThreshold: number;
  industryStats: IndustryAuctionStat[];
  onHighOpenRiskThresholdChange: (value: number) => void;
  onSelectAuctionSortMode: (mode: AuctionSortMode) => void;
  onSelectIndustry: (industry: string) => void;
  onSelectTier: (tier: AuctionTierFilter) => void;
  tierFilter: AuctionTierFilter;
  totalCount: number;
}) {
  return (
    <div className="workbench-panel-divider flex flex-col gap-2 border-b px-4 py-2.5">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="shrink-0 text-xs font-black text-[#7b756d]">排序</span>
        <Segmented
          className="max-w-full overflow-x-auto"
          onChange={(value) => onSelectAuctionSortMode(value as AuctionSortMode)}
          options={AUCTION_SORT_OPTIONS}
          size="small"
          value={auctionSortMode}
        />
        <span className="text-xs text-[#7b756d]">{getAuctionSortDescription(auctionSortMode)}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="shrink-0 text-xs font-black text-[#7b756d]">分层</span>
        {TIER_FILTERS.map((item) => (
          <Button
            key={item.value}
            onClick={() => onSelectTier(item.value)}
            size="small"
            type={tierFilter === item.value ? "primary" : "default"}
          >
            {item.label}
          </Button>
        ))}
        <span className="ml-0 shrink-0 text-xs font-black text-[#7b756d] lg:ml-2">高开风险阈值</span>
        <InputNumber
          className="w-[88px]"
          max={20}
          min={1}
          onChange={(value) => onHighOpenRiskThresholdChange(Number(value ?? 7))}
          precision={1}
          size="small"
          step={0.5}
          value={highOpenRiskThreshold}
        />
        <span className="text-xs text-[#7b756d]">% · {concentrationMessage}</span>
      </div>
      <IndustryQuickFilter
        activeIndustry={activeIndustry}
        industryStats={industryStats}
        onSelectIndustry={onSelectIndustry}
        totalCount={totalCount}
      />
    </div>
  );
}

function AuctionReviewPanel({
  finalizing,
  loading,
  onFinalize,
  summary,
}: {
  finalizing: boolean;
  loading: boolean;
  onFinalize: () => void;
  summary: AuctionReviewSummary | null;
}) {
  const failures = useMemo(() => buildFailureSamples(summary?.records ?? []), [summary]);
  return (
    <section className="workbench-panel mt-4 rounded-xl border">
      <div className="workbench-panel-divider flex flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-sm font-black text-[#11100e]">竞价复盘</div>
          <div className="text-xs text-[#7b756d]">
            按 10:00 强度、当日结果和次日反馈归因，持续校准竞价规则。
          </div>
        </div>
        <Button icon={<ReloadOutlined />} loading={finalizing} onClick={onFinalize} type="primary">
          生成/刷新今日复盘
        </Button>
      </div>
      <div className="grid gap-3 p-3 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <div className="grid grid-cols-2 gap-2">
          <MetricCard compact label="复盘样本" value={summary?.record_count ?? null} suffix="只" />
          <MetricCard compact label="已完成" value={summary?.completed_count ?? null} suffix="只" tone="red" />
          <MetricCard compact label="待归因" value={summary?.pending_count ?? null} suffix="只" />
          <MetricCard compact label="数据缺口" value={summary?.data_incomplete_count ?? null} suffix="只" tone="amber" />
        </div>
        <section className="rounded-lg border border-[#e3ddd3] bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-[#eee7db] px-3 py-2">
            <div>
              <div className="text-sm font-black text-[#11100e]">规则统计</div>
              <div className="text-xs text-[#7b756d]">{summary?.trade_date ?? "暂无复盘日期"} · 规则分桶表现</div>
            </div>
            <Tag color={summary?.buckets.length ? "red" : "default"}>{summary?.buckets.length ?? 0} 组</Tag>
          </div>
          <Table<AuctionRuleBucket>
            columns={[
              {
                title: "规则",
                dataIndex: "rule_tag",
                width: 110,
                render: (value: string) => <span className="font-black text-[#11100e]">{value}</span>,
              },
              {
                title: "样本",
                dataIndex: "sample_count",
                align: "right",
                width: 70,
              },
              {
                title: "胜率",
                dataIndex: "win_rate",
                align: "right",
                width: 82,
                render: (value: number | null) => (value === null ? "--" : `${(value * 100).toFixed(0)}%`),
              },
              {
                title: "均分",
                dataIndex: "avg_score",
                align: "right",
                width: 82,
                render: (value: number | null) => formatNumber(value),
              },
              {
                title: "建议",
                dataIndex: "suggestion",
                render: (value: string) => <span className="text-xs text-[#7b756d]">{value}</span>,
              },
            ]}
            dataSource={summary?.buckets ?? []}
            loading={loading}
            locale={{ emptyText: "暂无规则统计" }}
            pagination={false}
            rowKey="rule_tag"
            size="small"
          />
        </section>
        <section className="rounded-lg border border-[#e3ddd3] bg-white">
          <div className="border-b border-[#eee7db] px-3 py-2">
            <div className="text-sm font-black text-[#11100e]">失败样本</div>
            <div className="text-xs text-[#7b756d]">高分但当日表现偏弱的样本，用来反推过滤条件。</div>
          </div>
          <div className="space-y-2 p-3">
            {loading ? (
              <SkeletonRows />
            ) : failures.length ? (
              failures.map((item) => (
                <Link className="block rounded-lg border border-[#eee7db] p-2 hover:border-[#d92d20]" href={auctionStockHref(item)} key={`${item.trade_date}-${item.symbol}-${item.selected_at_label}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-black text-[#11100e]">{item.name || item.symbol}</span>
                    <Tag color="orange">{formatNumber(item.score.total_score)}</Tag>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-xs text-[#7b756d]">
                    <span>{item.selected_at_label}</span>
                    <span>收盘 {formatPct(item.day_result.close_pct)}</span>
                    <span>回撤 {formatPct(item.day_result.drawdown_pct)}</span>
                  </div>
                </Link>
              ))
            ) : (
              <Empty description="暂无失败样本" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function IndustryQuickFilter({
  activeIndustry,
  industryStats,
  onSelectIndustry,
  totalCount,
}: {
  activeIndustry: string;
  industryStats: IndustryAuctionStat[];
  onSelectIndustry: (industry: string) => void;
  totalCount: number;
}) {
  const hotIndustryStats = selectAuctionHotIndustryItems(industryStats);
  const focusIndustryStats = selectAuctionFocusIndustryItems(industryStats, hotIndustryStats);
  const pinnedIndustryValues = new Set(hotIndustryStats.map((item) => item.industry));
  for (const item of focusIndustryStats) {
    pinnedIndustryValues.add(item.industry);
  }
  const moreValue =
    activeIndustry !== "all" && !pinnedIndustryValues.has(activeIndustry) ? activeIndustry : undefined;
  const moreOptions = industryStats.map((item) => ({
    label: `${item.industry} ${item.count}`,
    value: item.industry,
  }));
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="shrink-0 text-xs font-black text-[#7b756d]">行业筛选</span>
        <div
          aria-label="热门行业快捷筛选"
          className="-my-1 flex min-w-0 flex-1 gap-1 overflow-x-auto py-1"
          role="group"
        >
          <Button
            className="shrink-0"
            onClick={() => onSelectIndustry("all")}
            size="small"
            type={activeIndustry === "all" ? "primary" : "default"}
          >
            全部行业
            <span className={activeIndustry === "all" ? "ml-1 opacity-80" : "ml-1 text-[#7b756d]"}>
              {totalCount}
            </span>
          </Button>
          {hotIndustryStats.map((item) => (
            <Button
              className="shrink-0"
              key={item.industry}
              onClick={() => onSelectIndustry(item.industry)}
              size="small"
              type={activeIndustry === item.industry ? "primary" : "default"}
            >
              {item.industry}
              <span className={activeIndustry === item.industry ? "ml-1 opacity-80" : "ml-1 text-[#7b756d]"}>
                {item.count}
              </span>
            </Button>
          ))}
        </div>
        <Select
          allowClear
          className="min-w-[150px] shrink-0"
          onChange={(value) => onSelectIndustry(value ?? "all")}
          optionFilterProp="label"
          options={moreOptions}
          placeholder="更多行业"
          showSearch
          size="small"
          value={moreValue}
        />
      </div>
      {focusIndustryStats.length ? (
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-xs font-black text-[#7b756d]">关注</span>
          <div className="-my-1 flex min-w-0 flex-1 gap-1 overflow-x-auto py-1" role="group" aria-label="关注行业筛选">
            {focusIndustryStats.map((item) => (
              <Button
                className="shrink-0"
                key={item.industry}
                onClick={() => onSelectIndustry(item.industry)}
                size="small"
                type={activeIndustry === item.industry ? "primary" : "default"}
              >
                {item.industry}
                <span className={activeIndustry === item.industry ? "ml-1 opacity-80" : "ml-1 text-[#7b756d]"}>
                  {item.count}
                </span>
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MainlineTopPanel({
  activeIndustry,
  industryStats,
  loading,
  onSelectIndustry,
  totalCount,
}: {
  activeIndustry: string;
  industryStats: IndustryAuctionStat[];
  loading: boolean;
  onSelectIndustry: (industry: string) => void;
  totalCount: number;
}) {
  return (
    <section className="workbench-panel rounded-xl border p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">主线行业 Top</div>
          <div className="text-xs text-[#7b756d]">看竞价是否集中到少数方向。</div>
        </div>
        <Button onClick={() => onSelectIndustry("all")} size="small" type={activeIndustry === "all" ? "primary" : "default"}>
          全部
        </Button>
      </div>
      <div className="space-y-2">
        {loading ? (
          <SkeletonRows />
        ) : industryStats.length ? (
          selectAuctionMainlineTopItems(industryStats).map((item, index) => {
            const percent = totalCount > 0 ? Math.round((item.count / totalCount) * 100) : 0;
            return (
              <button
                className={`w-full rounded-lg border px-3 py-2 text-left transition ${
                  activeIndustry === item.industry ? "border-[#d92d20] bg-white" : "border-[#e3ddd3] bg-white hover:border-[#c9bca8]"
                }`}
                key={item.industry}
                onClick={() => onSelectIndustry(item.industry)}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-black text-[#11100e]">
                    {index + 1}. {item.industry}
                  </span>
                  <span className="text-xs font-black text-[#d92d20]">{item.count} 只</span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <Progress className="m-0 flex-1" percent={percent} showInfo={false} strokeColor="#d92d20" />
                  <span className="w-9 text-right text-xs font-semibold text-[#7b756d]">{percent}%</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#7b756d]">
                  <span>均开 {formatPct(item.avgOpenGapPct)}</span>
                  <span>强势 {item.strongCount}</span>
                  <span>{formatCny(item.turnoverCny)}</span>
                </div>
              </button>
            );
          })
        ) : (
          <Empty description="暂无行业数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </div>
    </section>
  );
}

function RiskFocusPanel({
  highOpenRiskThreshold,
  items,
  loading,
}: {
  highOpenRiskThreshold: number;
  items: AuctionSnapshotItem[];
  loading: boolean;
}) {
  return (
    <section className="workbench-panel rounded-xl border p-3">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-[#11100e]">风险与观察</div>
          <div className="text-xs text-[#7b756d]">高开 {highOpenRiskThreshold}% 以上、低开转强和风险标记优先看。</div>
        </div>
        <Tag color={items.length ? "orange" : "default"}>{items.length} 条</Tag>
      </div>
      <div className="space-y-2">
        {loading ? (
          <SkeletonRows />
        ) : items.length ? (
          selectAuctionRiskFocusItems(items).map((item) => (
            <Link
              className="block rounded-lg border border-[#e3ddd3] bg-white px-3 py-2 no-underline transition hover:border-[#c9bca8]"
              href={auctionStockHref(item)}
              key={item.symbol}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-black text-[#11100e]">{item.name || item.symbol}</span>
                <span className="text-xs font-black text-[#d92d20]">{formatPct(item.open_gap_pct)}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-[#7b756d]">
                <span>{item.symbol}</span>
                <span>{item.industry || "--"}</span>
                <Tag color={tierColor(item.tier)}>{tierLabel(item.tier)}</Tag>
              </div>
            </Link>
          ))
        ) : (
          <Empty description="暂无风险提示" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </div>
    </section>
  );
}

function AuctionTimelinePanel({ timeline }: { timeline: AuctionTimelineResponse | null }) {
  const points = timeline?.points ?? [];
  const appearances = useMemo(() => buildTimelineAppearances(points), [points]);
  const latestCapturedLabel = [...points].reverse().find((point) => point.snapshot_status === "captured")?.label ?? null;
  return (
    <section className="workbench-panel rounded-xl border">
      <div className="workbench-panel-divider flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <div>
          <div className="text-sm font-black text-[#11100e]">竞价时间轴 · 阶段快照</div>
          <div className="text-xs text-[#7b756d]">锁定 09:20、09:23、09:24:50、09:25，先看候选数和强势延续。</div>
        </div>
        <Tag color="blue">连续出现优先，新晋谨慎确认</Tag>
      </div>
      <div className="grid gap-2 p-2 lg:grid-cols-4">
        {points.length ? (
          points.map((point) => (
            <div className="rounded-lg border border-[#e3ddd3] bg-white px-3 py-2" key={point.label}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-black text-[#11100e]">{point.label}</span>
                <Tag color={point.snapshot_status === "captured" ? "green" : "default"}>
                  {point.snapshot_status === "captured" ? "已锁定" : "等待"}
                </Tag>
              </div>
              <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
                <span className="rounded-md bg-[#faf7f1] px-2 py-1 text-[#7b756d]">候选 {point.metrics.candidate_count}</span>
                <span className="rounded-md bg-[#fff3f0] px-2 py-1 font-black text-[#d92d20]">
                  强势 {point.metrics.strong_high_open_count}
                </span>
              </div>
              {point.items[0] ? (
                <Link
                  className="mt-2 block rounded-md border border-[#eee8dc] bg-[#faf7f1] px-2 py-1.5 no-underline"
                  href={auctionStockHref(point.items[0])}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-xs font-black text-[#11100e]">
                      {point.items[0].name || point.items[0].symbol}
                    </span>
                    <span className="shrink-0 text-xs font-black text-[#d92d20]">
                      {formatPct(point.items[0].open_gap_pct)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {appearanceTag(point.items[0].symbol, point.label, latestCapturedLabel, appearances)}
                    <Tag>{point.items[0].industry || "未标注"}</Tag>
                  </div>
                </Link>
              ) : (
                <div className="mt-2 rounded-md border border-dashed border-[#e3ddd3] px-3 py-2 text-center text-xs text-[#7b756d]">
                  等待后台采样
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-[#e3ddd3] px-3 py-5 text-center text-xs text-[#7b756d] lg:col-span-4">
            暂无竞价时间轴快照
          </div>
        )}
      </div>
    </section>
  );
}

function AuctionTable({
  closePctBySymbol,
  items,
  loading,
  onAddToWatchlist,
  savingSymbol,
}: {
  closePctBySymbol: ReadonlyMap<string, number | null>;
  items: AuctionSnapshotItem[];
  loading: boolean;
  onAddToWatchlist: (item: AuctionSnapshotItem) => void;
  savingSymbol: string | null;
}) {
  return (
    <Table<AuctionSnapshotItem>
      columns={[
        {
          title: "股票",
          dataIndex: "name",
          fixed: "left",
          width: 190,
          render: (_, item) => (
            <Link className="font-black text-[#11100e]" href={auctionStockHref(item)}>
              {item.name || item.symbol}
              <span className="ml-2 text-xs font-semibold text-[#7b756d]">{item.symbol}</span>
            </Link>
          ),
        },
        {
          title: "行业",
          dataIndex: "industry",
          width: 120,
          render: (value: string | null) => (
            <Typography.Text className="text-xs text-[#7b756d]">{value || "--"}</Typography.Text>
          ),
        },
        {
          title: "热门题材",
          dataIndex: "themes",
          width: 190,
          render: (_, item) => (
            <div className="min-w-[150px]">
              {item.themes.length ? (
                <div className="flex flex-wrap gap-1">
                  {item.theme_resonance ? <Tag color="red">题材共振</Tag> : null}
                  <Tag color={item.hot_theme_rank !== null && item.hot_theme_rank <= 10 ? "orange" : "default"}>
                    {item.themes[0]} #{item.hot_theme_rank ?? "--"}
                  </Tag>
                  {item.theme_auction_rank ? <Tag>题材内 {item.theme_auction_rank}</Tag> : null}
                </div>
              ) : (
                <span className="text-xs text-[#7b756d]">--</span>
              )}
            </div>
          ),
        },
        {
          title: "竞价强度",
          dataIndex: "auction_score",
          width: 150,
          render: (value: number) => (
            <div className="min-w-[120px]">
              <Progress percent={Math.max(0, Math.min(value, 100))} showInfo={false} strokeColor="#d92d20" />
              <div className="mt-1 text-xs font-black text-[#11100e]">{value.toFixed(1)}</div>
            </div>
          ),
          sorter: (a, b) => a.auction_score - b.auction_score,
        },
        {
          title: "开盘涨幅",
          dataIndex: "open_gap_pct",
          align: "right",
          width: 110,
          render: (value: number | null) => <PctValue value={value} />,
          sorter: (a, b) => (a.open_gap_pct ?? -999) - (b.open_gap_pct ?? -999),
        },
        {
          title: "收盘涨幅",
          dataIndex: "symbol",
          align: "right",
          width: 110,
          render: (_, item) => <PctValue value={closePctBySymbol.get(item.symbol) ?? null} />,
          sorter: (a, b) => (closePctBySymbol.get(a.symbol) ?? -999) - (closePctBySymbol.get(b.symbol) ?? -999),
        },
        {
          title: "成交额",
          dataIndex: "turnover_cny",
          align: "right",
          width: 120,
          render: (value: number | null) => formatCny(value),
          sorter: (a, b) => (a.turnover_cny ?? 0) - (b.turnover_cny ?? 0),
        },
        {
          title: "分层",
          dataIndex: "tier",
          width: 220,
          render: (_, item) => {
            const liquidityWarning = getAuctionLiquidityWarning(item);
            return (
              <div className="min-w-[180px]">
                <div className="flex flex-wrap gap-1">
                  <Tag color={tierColor(item.tier)}>{tierLabel(item.tier)}</Tag>
                  {liquidityWarning ? <Tag color="orange">{liquidityWarning}</Tag> : null}
                </div>
                <div className="mt-1 line-clamp-2 text-xs leading-5 text-[#7b756d]">{item.action_note}</div>
              </div>
            );
          },
        },
        {
          title: "操作",
          dataIndex: "symbol",
          width: 96,
          render: (_, item) => (
            <Button
              loading={savingSymbol === item.symbol}
              onClick={() => onAddToWatchlist(item)}
              size="small"
              type="link"
            >
              加入自选
            </Button>
          ),
        },
      ]}
      dataSource={items}
      loading={loading}
      pagination={{ pageSize: 20, showSizeChanger: true, size: "small" }}
      rowKey="symbol"
      scroll={{ x: 1120 }}
      size="small"
    />
  );
}

function RiskRow({ item }: { item: AuctionSnapshotItem }) {
  return (
    <Link
      className="block rounded-lg border border-[#e3ddd3] bg-white p-3 no-underline transition hover:border-[#c9bca8]"
      href={auctionStockHref(item)}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-black text-[#11100e]">{item.name || item.symbol}</span>
        <span className="text-xs font-black text-[#d92d20]">{formatPct(item.open_gap_pct)}</span>
      </div>
      <div className="mt-1 text-xs text-[#7b756d]">{item.symbol}</div>
      <div className="mt-1 text-xs text-[#7b756d]">行业 {item.industry || "--"}</div>
      <div className="mt-2 flex flex-wrap gap-1">
        {item.risk_flags.map((flag) => (
          <Tag color="orange" key={flag}>
            {flag}
          </Tag>
        ))}
      </div>
    </Link>
  );
}

function MetricCard({
  compact = false,
  formatter,
  label,
  suffix,
  tone = "ink",
  value,
}: {
  compact?: boolean;
  formatter?: (value: number | null) => string;
  label: string;
  suffix?: string;
  tone?: "red" | "amber" | "ink";
  value: number | null;
}) {
  const toneClass = tone === "red" ? "text-[#d92d20]" : tone === "amber" ? "text-[#b45309]" : "text-[#11100e]";
  return (
    <div className={`rounded-lg border border-[#e3ddd3] bg-white ${compact ? "px-3 py-2.5" : "px-4 py-3"}`}>
      <div className="text-xs font-black text-[#7b756d]">{label}</div>
      <div className={`${compact ? "mt-1 text-xl" : "mt-2 text-2xl"} font-black ${toneClass}`}>
        {formatter ? formatter(value) : value === null ? "--" : value}
        {!formatter && suffix ? <span className="ml-1 text-sm font-semibold text-[#7b756d]">{suffix}</span> : null}
      </div>
    </div>
  );
}

function SkeletonRows() {
  return (
    <>
      {[0, 1, 2, 3].map((item) => (
        <div className="rounded-lg border border-[#e3ddd3] bg-white p-3" key={item}>
          <div className="h-4 w-2/3 rounded bg-[#eee9df]" />
          <div className="mt-2 h-3 w-1/2 rounded bg-[#eee9df]" />
        </div>
      ))}
    </>
  );
}

function buildTimelineAppearances(points: AuctionTimelineResponse["points"]): Map<string, number> {
  const appearances = new Map<string, number>();
  for (const point of points) {
    if (point.snapshot_status !== "captured") {
      continue;
    }
    const symbols = new Set(point.items.map((item) => item.symbol));
    for (const symbol of symbols) {
      appearances.set(symbol, (appearances.get(symbol) ?? 0) + 1);
    }
  }
  return appearances;
}

function appearanceTag(
  symbol: string,
  pointLabel: string,
  latestCapturedLabel: string | null,
  appearances: Map<string, number>,
) {
  const count = appearances.get(symbol) ?? 0;
  if (count >= 2) {
    return (
      <Tag color="red" key="continuous">
        连续出现{count}次
      </Tag>
    );
  }
  if (pointLabel === latestCapturedLabel) {
    return (
      <Tag color="orange" key="new">
        新晋
      </Tag>
    );
  }
  return null;
}

function PctValue({ value }: { value: number | null }) {
  return (
    <span className={value !== null && value >= 0 ? "text-[#d92d20]" : "market-green-text"}>
      {formatPct(value)}
    </span>
  );
}

function tierLabel(value: AuctionSnapshotItem["tier"]): string {
  if (value === "strong_high_open") {
    return "强势高开";
  }
  if (value === "volume_leader") {
    return "放量活跃";
  }
  if (value === "risk_overheat") {
    return "高开过热";
  }
  if (value === "weak_low_open") {
    return "低开偏弱";
  }
  if (value === "reversal_watch") {
    return "低开观察";
  }
  return "中性";
}

function tierColor(value: AuctionSnapshotItem["tier"]): string {
  if (value === "risk_overheat") {
    return "orange";
  }
  if (value === "weak_low_open") {
    return "green";
  }
  if (value === "reversal_watch") {
    return "blue";
  }
  if (value === "volume_leader") {
    return "purple";
  }
  if (value === "strong_high_open") {
    return "red";
  }
  return "default";
}

function auctionModelBucketColor(value: AuctionModelPredictionItem["bucket"]): string {
  if (value === "selected") {
    return "red";
  }
  if (value === "attack") {
    return "orange";
  }
  if (value === "watch") {
    return "blue";
  }
  return "default";
}

function sessionLabel(value: string | null | undefined): string {
  if (value === "call_auction") {
    return "集合竞价中";
  }
  if (value === "pre_open") {
    return "开盘前撮合";
  }
  if (value === "continuous") {
    return "连续竞价";
  }
  if (value === "closed") {
    return "非交易时段";
  }
  return "等待数据";
}

function sessionColor(value: string | null | undefined): string {
  if (value === "call_auction" || value === "pre_open") {
    return "red";
  }
  if (value === "continuous") {
    return "green";
  }
  return "default";
}

function snapshotStatusLabel(value: AuctionSnapshotResponse["snapshot_status"] | null | undefined): string {
  if (value === "fresh") {
    return "实时刷新";
  }
  if (value === "cached") {
    return "缓存快照";
  }
  if (value === "stale") {
    return "快照偏旧";
  }
  if (value === "missing") {
    return "等待快照";
  }
  return "等待快照";
}

function snapshotStatusColor(value: AuctionSnapshotResponse["snapshot_status"] | null | undefined): string {
  if (value === "fresh" || value === "cached") {
    return "green";
  }
  if (value === "stale") {
    return "orange";
  }
  return "default";
}

function formatCacheAge(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "--";
  }
  if (value < 1) {
    return "<1秒";
  }
  if (value < 60) {
    return `${value.toFixed(0)}秒`;
  }
  return `${(value / 60).toFixed(1)}分钟`;
}

function formatPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(1);
}

function formatRatioPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatSignedRatioPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  const pct = value * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function formatRawPct(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatProbability(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatPrice(value: number | null): string {
  if (value === null) {
    return "--";
  }
  return value.toFixed(2);
}

function formatAuctionModelGeneratedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${min}`;
}

function formatCny(value: number | null): string {
  if (value === null) {
    return "--";
  }
  const abs = Math.abs(value);
  if (abs >= 1_0000_0000_0000) {
    return `${(value / 1_0000_0000_0000).toFixed(2)}万亿`;
  }
  if (abs >= 1_0000_0000) {
    return `${(value / 1_0000_0000).toFixed(2)}亿`;
  }
  if (abs >= 1_0000) {
    return `${(value / 1_0000).toFixed(2)}万`;
  }
  return value.toFixed(0);
}

function buildIndustryStats(items: AuctionSnapshotItem[]): IndustryAuctionStat[] {
  const stats = new Map<string, { count: number; gapTotal: number; gapCount: number; strongCount: number; turnoverCny: number }>();
  for (const item of items) {
    const industry = item.industry || "未标注";
    const current = stats.get(industry) ?? {
      count: 0,
      gapCount: 0,
      gapTotal: 0,
      strongCount: 0,
      turnoverCny: 0,
    };
    current.count += 1;
    current.turnoverCny += item.turnover_cny ?? 0;
    if (item.open_gap_pct !== null) {
      current.gapCount += 1;
      current.gapTotal += item.open_gap_pct;
      if (item.open_gap_pct >= 3) {
        current.strongCount += 1;
      }
    }
    stats.set(industry, current);
  }
  return Array.from(stats.entries())
    .map(([industry, value]) => ({
      avgOpenGapPct: value.gapCount ? value.gapTotal / value.gapCount : null,
      count: value.count,
      industry,
      strongCount: value.strongCount,
      turnoverCny: value.turnoverCny,
    }))
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return right.turnoverCny - left.turnoverCny;
    });
}

function buildIndustryConcentration(stats: IndustryAuctionStat[], totalCount: number): { label: string; message: string } {
  const top = stats[0];
  if (!top || totalCount <= 0) {
    return { label: "--", message: "主线集中度暂无数据。" };
  }
  const ratio = (top.count / totalCount) * 100;
  const label = `${top.industry} ${ratio.toFixed(0)}%`;
  if (ratio >= 18) {
    return { label, message: `主线集中度偏高，${top.industry} 是当前竞价首要观察方向。` };
  }
  if (ratio >= 10) {
    return { label, message: `主线集中度中等，${top.industry} 有一定聚集但仍需看开盘延续。` };
  }
  return { label, message: "主线集中度分散，早盘不要急着押单一方向。" };
}

function buildFailureSamples(records: AuctionReviewRecord[]): AuctionReviewRecord[] {
  return records
    .filter(
      (item) =>
        (item.score.total_score ?? 0) >= 45 &&
        ((item.day_result.close_pct ?? 0) < 0 || (item.day_result.drawdown_pct ?? 0) <= -5),
    )
    .sort(
      (left, right) =>
        (right.score.total_score ?? -999) - (left.score.total_score ?? -999) ||
        (left.day_result.close_pct ?? 0) - (right.day_result.close_pct ?? 0),
    )
    .slice(0, 5);
}

function buildAuctionWatchlistNote(item: AuctionSnapshotItem): string {
  return [
    "来源：竞价雷达",
    `行业：${item.industry || "--"}`,
    `开盘幅度：${formatPct(item.open_gap_pct)}`,
    `当前涨幅：${formatPct(item.current_pct_change)}`,
    `成交额：${formatCny(item.turnover_cny)}`,
    `分层：${tierLabel(item.tier)}`,
    `操作备注：${item.action_note || "--"}`,
  ].join("；");
}

function buildAuctionModelWatchlistNote(
  item: AuctionModelPredictionItem,
  run: AuctionModelTop3Response | null,
): string {
  return [
    "来源：竞价模型Top3",
    `目标日期：${run?.trade_date ?? "--"}`,
    `特征日：${item.feature_end_date || run?.feature_end_date || "--"}`,
    `概率：${formatProbability(item.prob_3pct)}`,
    `分组：${auctionModelBucketLabel(item.bucket)}`,
    `前收：${formatPrice(item.prev_close_price)}`,
    `守卫：${item.guard_rule || run?.guard_rule || "--"}`,
    "说明：研究信号，实盘需结合09:25竞价和10:00守卫确认",
  ].join("；");
}

function auctionStockHref(item: { industry?: string | null; name?: string | null; symbol: string }): string {
  return buildStockDetailHref(item.symbol, {
    from: "auction",
    industry: item.industry,
    name: item.name,
  });
}

function modelStockHref(item: { name?: string | null; symbol: string }): string {
  return buildStockDetailHref(item.symbol, {
    from: "auction-model",
    name: item.name,
  });
}

function todayDate(): string {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function nextWeekdayDate(): string {
  const date = new Date();
  const day = date.getDay();
  if (day === 6) {
    date.setDate(date.getDate() + 2);
  } else if (day === 0) {
    date.setDate(date.getDate() + 1);
  }
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

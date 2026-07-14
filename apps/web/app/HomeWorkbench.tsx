"use client";

import { useEffect, useRef, useState } from "react";
import { ScreenerWorkbench } from "../components/ScreenerWorkbench";
import {
  addWatchlistPoolItem,
  createScreenRunJob,
  getDataSourceStatus,
  getCzscShadowScreeningJob,
  getLatestScreenRun,
  getMarketOverview,
  getScreenRunJob,
  getSectorRadar,
  getSentimentSummary,
  getWatchlistPool,
} from "../lib/api";
import { mergeShadowScores, shadowScoresBySymbol } from "../lib/czscShadow";
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

const SCREEN_FILTERS_STORAGE_KEY = "strong-stock-screen-filters";

export function HomeWorkbench() {
  const [tradeDate, setTradeDate] = useState(defaultTradeDate());
  const [sources, setSources] = useState<DataSourceStatusResponse | null>(null);
  const [marketOverview, setMarketOverview] = useState<MarketOverviewResponse | null>(null);
  const [sectorRadar, setSectorRadar] = useState<SectorRadarResponse | null>(null);
  const [sentimentSummary, setSentimentSummary] = useState<SentimentSummaryResponse | null>(null);
  const [result, setResult] = useState<StrongStockScreeningResponse | null>(null);
  const [intraday, setIntraday] = useState<StrongStockIntradaySnapshot | null>(null);
  const [strategy, setStrategy] = useState<ScreenStrategy>("combined");
  const [scanLimit, setScanLimit] = useState(160);
  const [screenFilters, setScreenFilters] = useState<ScreenRunFilters>({});
  const [screenFiltersSaved, setScreenFiltersSaved] = useState(false);
  const [watchlistPoolItems, setWatchlistPoolItems] = useState<WatchlistPoolItem[]>([]);
  const [marketSupportLoaded, setMarketSupportLoaded] = useState(false);
  const [marketSupportLoading, setMarketSupportLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [screenJob, setScreenJob] = useState<ScreenRunJobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchlistMessage, setWatchlistMessage] = useState<string | null>(null);
  const [czscResearchMessage, setCzscResearchMessage] = useState<string | null>(null);
  const screenRunPollerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const czscShadowPollerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const czscShadowGenerationRef = useRef(0);

  useEffect(() => {
    setScreenFilters(loadSavedScreenFilters());
    void refreshSources();
    void refreshMarketOverview();
    void refreshSentimentSummary();
    void refreshLatest();
    void refreshWatchlistPool();

    return () => {
      if (screenRunPollerRef.current) {
        clearTimeout(screenRunPollerRef.current);
      }
      stopCzscShadowPolling();
    };
  }, []);

  async function refreshSources() {
    try {
      setSources(await getDataSourceStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取数据源状态失败");
    }
  }

  async function refreshMarketOverview() {
    try {
      setMarketOverview(await getMarketOverview());
    } catch (err) {
      setMarketOverview(null);
      setError(err instanceof Error ? err.message : "读取全A市场概览失败");
    }
  }

  async function refreshSectorRadar() {
    try {
      setSectorRadar(await getSectorRadar(20));
    } catch (err) {
      setSectorRadar(null);
      setError(err instanceof Error ? err.message : "读取板块资金流失败");
    }
  }

  async function handleLoadMarketSupport() {
    if (marketSupportLoaded || marketSupportLoading) {
      return;
    }
    setMarketSupportLoading(true);
    try {
      await refreshSectorRadar();
      setMarketSupportLoaded(true);
    } finally {
      setMarketSupportLoading(false);
    }
  }

  async function refreshSentimentSummary() {
    try {
      setSentimentSummary(await getSentimentSummary(tradeDate, 80, false));
    } catch {
      setSentimentSummary(null);
    }
  }

  async function refreshLatest() {
    try {
      applyFormalResult(await getLatestScreenRun());
    } catch {
      setResult(null);
    }
  }

  async function refreshWatchlistPool() {
    try {
      const response = await getWatchlistPool();
      setWatchlistPoolItems(response.items);
    } catch {
      setWatchlistPoolItems([]);
    }
  }

  async function handleRun() {
    if (screenRunPollerRef.current) {
      clearTimeout(screenRunPollerRef.current);
    }
    stopCzscShadowPolling();
    setRunning(true);
    setError(null);
    setScreenJob(null);
    try {
      const job = await createScreenRunJob(tradeDate, 30, scanLimit, screenFilters, { strategy });
      handleScreenRunJobState(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行筛选失败");
      setRunning(false);
    }
  }

  function handleScreenRunJobState(job: ScreenRunJobState) {
    setScreenJob(job);
    if (job.status === "success") {
      setRunning(false);
      if (job.result) {
        applyFormalResult(job.result);
        setIntraday(null);
      } else {
        void refreshLatest();
      }
      void Promise.all([refreshSources(), refreshMarketOverview(), refreshSectorRadar(), refreshSentimentSummary()]);
      return;
    }
    if (job.status === "failed" || job.status === "canceled") {
      setRunning(false);
      setError(job.error ?? (job.status === "canceled" ? "筛选任务已取消" : "筛选任务失败"));
      return;
    }
    pollScreenRunJob(job.job_id);
  }

  function pollScreenRunJob(jobId: string) {
    if (screenRunPollerRef.current) {
      clearTimeout(screenRunPollerRef.current);
    }
    screenRunPollerRef.current = setTimeout(() => {
      void (async () => {
        try {
          handleScreenRunJobState(await getScreenRunJob(jobId));
        } catch (err) {
          setRunning(false);
          setError(err instanceof Error ? err.message : "读取筛选任务失败");
        }
      })();
    }, 2000);
  }

  function stopCzscShadowPolling() {
    czscShadowGenerationRef.current += 1;
    if (czscShadowPollerRef.current) {
      clearTimeout(czscShadowPollerRef.current);
      czscShadowPollerRef.current = null;
    }
  }

  function applyFormalResult(next: StrongStockScreeningResponse) {
    stopCzscShadowPolling();
    setCzscResearchMessage(null);
    setResult(next);
    if (!next.czsc_v2_job_id) {
      return;
    }
    pollCzscShadowJob(next.czsc_v2_job_id, next.trade_date, czscShadowGenerationRef.current);
  }

  function pollCzscShadowJob(jobId: string, resultTradeDate: string, generation: number) {
    czscShadowPollerRef.current = setTimeout(() => {
      void (async () => {
        try {
          const response = await getCzscShadowScreeningJob(jobId);
          if (czscShadowGenerationRef.current !== generation) {
            return;
          }
          const batch = response.batch;
          if (batch) {
            setResult((current) => {
              if (!current || current.trade_date !== resultTradeDate) {
                return current;
              }
              return {
                ...current,
                czsc_v2_status: batch.status,
                items: mergeShadowScores(current.items, shadowScoresBySymbol(batch)),
              };
            });
            if (batch.status !== "pending") {
              return;
            }
          }
          if (response.job.status === "failed" || response.job.status === "canceled") {
            setCzscResearchMessage("CZSC研究暂不可用");
            return;
          }
          pollCzscShadowJob(jobId, resultTradeDate, generation);
        } catch {
          if (czscShadowGenerationRef.current === generation) {
            setCzscResearchMessage("CZSC研究暂不可用");
          }
        }
      })();
    }, 1200);
  }

  function handleSaveScreenFilters() {
    window.localStorage.setItem(SCREEN_FILTERS_STORAGE_KEY, JSON.stringify(screenFilters));
    setScreenFiltersSaved(true);
  }

  function handleScreenFiltersChange(value: ScreenRunFilters) {
    setScreenFilters(value);
    setScreenFiltersSaved(false);
  }

  async function handleAddToWatchlist(item: StrongStockScreeningItem, group: string, tags: string[]) {
    setError(null);
    setWatchlistMessage(null);
    try {
      const response = await addWatchlistPoolItem({
        symbol: item.symbol,
        name: item.name,
        industry: item.industry,
        group: group.trim() || "自选",
        tags,
        note: null,
      });
      setWatchlistPoolItems(response.items);
      setWatchlistMessage(`已加入自选：${item.name} ${item.symbol}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入自选股失败");
    }
  }

  async function handleAddManyToWatchlist(items: StrongStockScreeningItem[], group: string, tags: string[]) {
    if (items.length === 0) {
      return;
    }
    setError(null);
    setWatchlistMessage(null);
    try {
      let latestItems = watchlistPoolItems;
      for (const item of items) {
        const response = await addWatchlistPoolItem({
          symbol: item.symbol,
          name: item.name,
          industry: item.industry,
          group: group.trim() || "自选",
          tags,
          note: null,
        });
        latestItems = response.items;
      }
      setWatchlistPoolItems(latestItems);
      setWatchlistMessage(`已加入自选：${items.length} 只`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量加入自选股失败");
    }
  }

  return (
    <ScreenerWorkbench
      error={error}
      czscResearchMessage={czscResearchMessage}
      intraday={intraday}
      marketOverview={marketOverview}
      marketSupportLoading={marketSupportLoading}
      sectorRadar={sectorRadar}
      sentimentSummary={sentimentSummary}
      onRefreshSources={() => void Promise.all([refreshSources(), refreshMarketOverview(), refreshSectorRadar(), refreshSentimentSummary()])}
      onRun={() => void handleRun()}
      onLoadMarketSupport={() => void handleLoadMarketSupport()}
      onAddToWatchlist={(item, group, tags) => void handleAddToWatchlist(item, group, tags)}
      onAddManyToWatchlist={(items, group, tags) => void handleAddManyToWatchlist(items, group, tags)}
      onSaveScreenFilters={handleSaveScreenFilters}
      result={result}
      running={running}
      scanLimit={scanLimit}
      screenJob={screenJob}
      screenFilters={screenFilters}
      screenFiltersSaved={screenFiltersSaved}
      sources={sources}
      strategy={strategy}
      tradeDate={tradeDate}
      onScanLimitChange={setScanLimit}
      onScreenFiltersChange={handleScreenFiltersChange}
      onStrategyChange={setStrategy}
      onTradeDateChange={(nextTradeDate) => {
        if (nextTradeDate !== tradeDate) {
          stopCzscShadowPolling();
        }
        setTradeDate(nextTradeDate);
      }}
      watchlistPoolItems={watchlistPoolItems}
      watchlistMessage={watchlistMessage}
    />
  );
}

function loadSavedScreenFilters(): ScreenRunFilters {
  if (typeof window === "undefined") {
    return {};
  }
  const rawValue = window.localStorage.getItem(SCREEN_FILTERS_STORAGE_KEY);
  if (!rawValue) {
    return {};
  }
  try {
    return sanitizeScreenFilters(JSON.parse(rawValue));
  } catch {
    return {};
  }
}

function sanitizeScreenFilters(value: unknown): ScreenRunFilters {
  if (!value || typeof value !== "object") {
    return {};
  }
  const source = value as Record<string, unknown>;
  const filters: ScreenRunFilters = {};
  if (typeof source.min_market_cap_billion === "number") {
    filters.min_market_cap_billion = source.min_market_cap_billion;
  }
  if (typeof source.max_market_cap_billion === "number") {
    filters.max_market_cap_billion = source.max_market_cap_billion;
  }
  if (typeof source.kdj_j_max === "number") {
    filters.kdj_j_max = source.kdj_j_max;
  }
  if (typeof source.chanlun_min_confluence_score === "number") {
    filters.chanlun_min_confluence_score = Math.max(0, Math.min(100, source.chanlun_min_confluence_score));
  }
  if (source.chanlun_require_confirmed_buy === true) {
    filters.chanlun_require_confirmed_buy = true;
  }
  if (Array.isArray(source.industries)) {
    filters.industries = source.industries.filter((item): item is string => typeof item === "string");
  }
  if (Array.isArray(source.market_types)) {
    filters.market_types = source.market_types.filter(isMarketType);
  }
  return filters;
}

function isMarketType(value: unknown): value is NonNullable<ScreenRunFilters["market_types"]>[number] {
  return value === "main" || value === "gem" || value === "star" || value === "bj";
}

function defaultTradeDate(): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

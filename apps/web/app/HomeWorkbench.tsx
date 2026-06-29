"use client";

import { useEffect, useState } from "react";
import { ScreenerWorkbench } from "../components/ScreenerWorkbench";
import {
  addWatchlistPoolItem,
  createScreenRun,
  getDataSourceStatus,
  getLatestScreenRun,
  getMarketOverview,
  getSectorRadar,
  getWatchlistPool,
  recheckGsgfReview,
  runGsgfCalibration,
  saveLatestGsgfReviewSnapshot,
} from "../lib/api";
import type {
  DataSourceStatusResponse,
  GsgfRealCalibrationSummary,
  GsgfReviewSummary,
  MarketOverviewResponse,
  ScreenRunFilters,
  ScreenStrategy,
  SectorRadarResponse,
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
  const [result, setResult] = useState<StrongStockScreeningResponse | null>(null);
  const [intraday, setIntraday] = useState<StrongStockIntradaySnapshot | null>(null);
  const [strategy, setStrategy] = useState<ScreenStrategy>("combined");
  const [scanLimit, setScanLimit] = useState(160);
  const [screenFilters, setScreenFilters] = useState<ScreenRunFilters>({});
  const [screenFiltersSaved, setScreenFiltersSaved] = useState(false);
  const [watchlistPoolItems, setWatchlistPoolItems] = useState<WatchlistPoolItem[]>([]);
  const [reviewSummary, setReviewSummary] = useState<GsgfReviewSummary | null>(null);
  const [reviewRunning, setReviewRunning] = useState(false);
  const [calibrationSummary, setCalibrationSummary] = useState<GsgfRealCalibrationSummary | null>(null);
  const [calibrationRunning, setCalibrationRunning] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchlistMessage, setWatchlistMessage] = useState<string | null>(null);

  useEffect(() => {
    setScreenFilters(loadSavedScreenFilters());
    void refreshSources();
    void refreshMarketOverview();
    void refreshSectorRadar();
    void refreshLatest();
    void refreshWatchlistPool();
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

  async function refreshLatest() {
    try {
      setResult(await getLatestScreenRun());
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
    setRunning(true);
    setError(null);
    try {
      const response = await createScreenRun(tradeDate, 30, scanLimit, screenFilters, { strategy });
      setResult(response);
      setIntraday(null);
      await Promise.all([refreshSources(), refreshMarketOverview(), refreshSectorRadar()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行筛选失败");
    } finally {
      setRunning(false);
    }
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

  async function handleSaveGsgfReviewSnapshot() {
    setReviewRunning(true);
    setError(null);
    try {
      await saveLatestGsgfReviewSnapshot();
      setReviewSummary(await recheckGsgfReview({ windows: [1, 3, 5, 10], count: 180 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存股是股非复盘快照失败");
    } finally {
      setReviewRunning(false);
    }
  }

  async function handleRecheckGsgfReview() {
    setReviewRunning(true);
    setError(null);
    try {
      setReviewSummary(await recheckGsgfReview({ windows: [1, 3, 5, 10], count: 180 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "复查股是股非信号失败");
    } finally {
      setReviewRunning(false);
    }
  }

  async function handleRunGsgfCalibration(options: {
    tradeDatesText: string;
    windowsText: string;
    scanLimit: number;
    count: number;
  }) {
    const tradeDates = splitInputList(options.tradeDatesText || tradeDate);
    if (tradeDates.length === 0) {
      setError("请输入至少一个校准样本日");
      return;
    }
    setCalibrationRunning(true);
    setError(null);
    try {
      setCalibrationSummary(
        await runGsgfCalibration({
          tradeDates,
          windows: splitNumberList(options.windowsText, [1, 3, 5, 10]),
          scanLimit: options.scanLimit,
          count: options.count,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行股是股非真实样本校准失败");
    } finally {
      setCalibrationRunning(false);
    }
  }

  return (
    <ScreenerWorkbench
      calibrationRunning={calibrationRunning}
      calibrationSummary={calibrationSummary}
      error={error}
      intraday={intraday}
      marketOverview={marketOverview}
      sectorRadar={sectorRadar}
      onRefreshSources={() => void Promise.all([refreshSources(), refreshMarketOverview(), refreshSectorRadar()])}
      onRun={() => void handleRun()}
      onRunGsgfCalibration={(options) => void handleRunGsgfCalibration(options)}
      onRecheckGsgfReview={() => void handleRecheckGsgfReview()}
      onAddToWatchlist={(item, group, tags) => void handleAddToWatchlist(item, group, tags)}
      onAddManyToWatchlist={(items, group, tags) => void handleAddManyToWatchlist(items, group, tags)}
      onSaveScreenFilters={handleSaveScreenFilters}
      onSaveGsgfReviewSnapshot={() => void handleSaveGsgfReviewSnapshot()}
      result={result}
      reviewRunning={reviewRunning}
      reviewSummary={reviewSummary}
      running={running}
      scanLimit={scanLimit}
      screenFilters={screenFilters}
      screenFiltersSaved={screenFiltersSaved}
      sources={sources}
      strategy={strategy}
      tradeDate={tradeDate}
      onScanLimitChange={setScanLimit}
      onScreenFiltersChange={handleScreenFiltersChange}
      onStrategyChange={setStrategy}
      onTradeDateChange={setTradeDate}
      watchlistPoolItems={watchlistPoolItems}
      watchlistMessage={watchlistMessage}
    />
  );
}

function splitInputList(value: string): string[] {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const chunk of value.split(/[,，\s]+/)) {
    const item = chunk.trim();
    if (item && !seen.has(item)) {
      seen.add(item);
      output.push(item);
    }
  }
  return output;
}

function splitNumberList(value: string, fallback: number[]): number[] {
  const output: number[] = [];
  const seen = new Set<number>();
  for (const item of splitInputList(value)) {
    const parsed = Number(item);
    if (Number.isInteger(parsed) && parsed > 0 && !seen.has(parsed)) {
      seen.add(parsed);
      output.push(parsed);
    }
  }
  return output.length > 0 ? output : fallback;
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

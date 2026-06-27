"use client";

import { useEffect, useState } from "react";
import { ScreenerWorkbench } from "../components/ScreenerWorkbench";
import {
  addWatchlistPoolItem,
  createScreenRun,
  getDataSourceStatus,
  getLatestScreenRun,
  getWatchlistPool,
} from "../lib/api";
import type {
  DataSourceStatusResponse,
  ScreenRunFilters,
  ScreenStrategy,
  StrongStockIntradaySnapshot,
  StrongStockScreeningItem,
  StrongStockScreeningResponse,
  WatchlistPoolItem,
} from "../lib/types";

const SCREEN_FILTERS_STORAGE_KEY = "strong-stock-screen-filters";

export default function HomePage() {
  const [tradeDate, setTradeDate] = useState(defaultTradeDate());
  const [sources, setSources] = useState<DataSourceStatusResponse | null>(null);
  const [result, setResult] = useState<StrongStockScreeningResponse | null>(null);
  const [intraday, setIntraday] = useState<StrongStockIntradaySnapshot | null>(null);
  const [strategy, setStrategy] = useState<ScreenStrategy>("combined");
  const [scanLimit, setScanLimit] = useState(40);
  const [screenFilters, setScreenFilters] = useState<ScreenRunFilters>({});
  const [screenFiltersSaved, setScreenFiltersSaved] = useState(false);
  const [watchlistPoolItems, setWatchlistPoolItems] = useState<WatchlistPoolItem[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [watchlistMessage, setWatchlistMessage] = useState<string | null>(null);

  useEffect(() => {
    setScreenFilters(loadSavedScreenFilters());
    void refreshSources();
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
      await refreshSources();
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

  return (
    <ScreenerWorkbench
      error={error}
      intraday={intraday}
      onRefreshSources={() => void refreshSources()}
      onRun={() => void handleRun()}
      onAddToWatchlist={(item, group, tags) => void handleAddToWatchlist(item, group, tags)}
      onAddManyToWatchlist={(items, group, tags) => void handleAddManyToWatchlist(items, group, tags)}
      onSaveScreenFilters={handleSaveScreenFilters}
      result={result}
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

import type {
  DataSourceStatusResponse,
  GsgfAnalysis,
  GsgfBacktestSummary,
  GsgfRealCalibrationSummary,
  GsgfReviewSnapshotResponse,
  GsgfReviewSummary,
  GsgfTradePlan,
  MarketEmotionSnapshotResponse,
  MarketOverviewResponse,
  NotificationChannelConfig,
  NotificationSendResult,
  RuntimeSettingsHealthResponse,
  RuntimeSettingsResponse,
  ScreenRunFilters,
  ScreenStrategy,
  SectorRadarResponse,
  SentimentDetailResponse,
  SentimentSummaryResponse,
  SentimentMonitorConfig,
  SentimentMonitorStatus,
  ShortTermIntradaySentimentResponse,
  ShortTermIntradaySignalDigest,
  ShortTermSentimentResponse,
  StockKlineResponse,
  StockResearchResponse,
  StrongStockIntradaySnapshot,
  StrongStockScreeningResponse,
  WatchlistGsgfStatusResponse,
  WatchlistPoolItemRequest,
  WatchlistPoolResponse,
} from "./types";

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.location.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8010`;
  }
  return "http://localhost:8010";
}

const API_BASE_URL = process.env.NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL ?? defaultApiBaseUrl();

export async function getDataSourceStatus(): Promise<DataSourceStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/data-sources/status`);
  if (!response.ok) {
    throw new Error(`读取数据源状态失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<DataSourceStatusResponse>;
}

export async function getMarketOverview(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/market/overview`);
  if (!response.ok) {
    throw new Error(`读取全A市场概览失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<MarketOverviewResponse>;
}

export async function getSectorRadar(limit = 20): Promise<SectorRadarResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sectors/radar?limit=${encodeURIComponent(limit)}`);
  if (!response.ok) {
    throw new Error(`读取板块资金流失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SectorRadarResponse>;
}

export async function getShortTermSentiment(tradeDate: string, limit = 50): Promise<ShortTermSentimentResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取短线情绪失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ShortTermSentimentResponse>;
}

export async function getSentimentSummary(
  tradeDate: string,
  limit = 80,
  refresh = false,
): Promise<SentimentSummaryResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    refresh: String(refresh),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/summary?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取短线情绪概览失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentSummaryResponse>;
}

export async function getSentimentDetail(
  tradeDate: string,
  limit = 80,
  refresh = false,
): Promise<SentimentDetailResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    refresh: String(refresh),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/detail?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取短线情绪详情失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentDetailResponse>;
}

export async function getMarketEmotionSnapshot(tradeDate: string, limit = 80): Promise<MarketEmotionSnapshotResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/market-emotion?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取市场情绪仪表盘失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<MarketEmotionSnapshotResponse>;
}

export async function getShortTermIntradaySentiment(
  tradeDate: string,
  limit = 80,
  period = "1m",
  count = 120,
): Promise<ShortTermIntradaySentimentResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    period,
    count: String(count),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/intraday?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`读取盘中情绪失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ShortTermIntradaySentimentResponse>;
}

export async function getShortTermIntradaySignalDigest(
  tradeDate: string,
  limit = 80,
  period = "1m",
  count = 120,
): Promise<ShortTermIntradaySignalDigest> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    period,
    count: String(count),
  });
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/intraday/digest?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`生成短线提醒草稿失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ShortTermIntradaySignalDigest>;
}

export async function getSentimentMonitorStatus(): Promise<SentimentMonitorStatus> {
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/monitor/status`);
  if (!response.ok) {
    throw new Error(`读取后台监控状态失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentMonitorStatus>;
}

export async function saveSentimentMonitorConfig(
  payload: SentimentMonitorConfig,
): Promise<SentimentMonitorStatus> {
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/monitor/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`保存后台监控配置失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentMonitorStatus>;
}

export async function startSentimentMonitor(): Promise<SentimentMonitorStatus> {
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/monitor/start`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`启动后台监控失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentMonitorStatus>;
}

export async function stopSentimentMonitor(): Promise<SentimentMonitorStatus> {
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/monitor/stop`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`停止后台监控失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentMonitorStatus>;
}

export async function runSentimentMonitorOnce(tradeDate?: string): Promise<SentimentMonitorStatus> {
  const suffix = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/short-term/sentiment/monitor/run-once${suffix}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`手动采样失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<SentimentMonitorStatus>;
}

export async function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings`);
  if (!response.ok) {
    throw new Error(`读取设置失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsResponse>;
}

export async function saveRuntimeSettings(payload: {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key?: string | null;
  tickflow_base_url: string;
  ifind_api_key?: string | null;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  provider_timeout_seconds: number;
  notification_channels?: NotificationChannelConfig[];
  sentiment_monitor?: SentimentMonitorConfig;
}): Promise<RuntimeSettingsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`保存设置失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsResponse>;
}

export async function sendNotificationMessage(payload: {
  title: string;
  message_text: string;
  channel_ids?: string[];
}): Promise<NotificationSendResult> {
  const response = await fetch(`${API_BASE_URL}/api/notifications/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`发送通知失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<NotificationSendResult>;
}

export async function checkRuntimeSettingsHealth(symbol = "605289.SH"): Promise<RuntimeSettingsHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/settings/health?symbol=${encodeURIComponent(symbol)}`);
  if (!response.ok) {
    throw new Error(`健康检查失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<RuntimeSettingsHealthResponse>;
}

export async function createScreenRun(
  tradeDate: string,
  limit = 30,
  scanLimit = 40,
  filters: ScreenRunFilters = {},
  options: {
    strategy?: ScreenStrategy;
    include_gsgf?: boolean;
    exclude_gsgf_hard_risk?: boolean;
  } = {},
): Promise<StrongStockScreeningResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screen/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate, limit, scan_limit: scanLimit, filters, ...options }),
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const payload = JSON.parse(detail) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep raw response text.
    }
    throw new Error(`运行筛选失败：${response.status} ${detail}`);
  }
  return response.json() as Promise<StrongStockScreeningResponse>;
}

export async function getLatestScreenRun(): Promise<StrongStockScreeningResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screen/runs/latest`);
  if (!response.ok) {
    throw new Error(`读取最近筛选失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<StrongStockScreeningResponse>;
}

export async function runGsgfBacktest({
  symbols,
  windows = [1, 3, 5, 10],
  minHistory = 60,
  count = 180,
}: {
  symbols: string[];
  windows?: number[];
  minHistory?: number;
  count?: number;
}): Promise<GsgfBacktestSummary> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbols,
      windows,
      min_history: minHistory,
      count,
    }),
  });
  if (!response.ok) {
    throw new Error(`运行股是股非回测失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfBacktestSummary>;
}

export async function runGsgfCalibration({
  tradeDates,
  windows = [1, 3, 5, 10],
  scanLimit = 80,
  count = 260,
}: {
  tradeDates: string[];
  windows?: number[];
  scanLimit?: number;
  count?: number;
}): Promise<GsgfRealCalibrationSummary> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/calibration`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trade_dates: tradeDates,
      windows,
      scan_limit: scanLimit,
      count,
    }),
  });
  if (!response.ok) {
    throw new Error(`运行股是股非真实样本校准失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfRealCalibrationSummary>;
}

export async function buildGsgfTradePlan(analysis: GsgfAnalysis): Promise<GsgfTradePlan> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/trade-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis }),
  });
  if (!response.ok) {
    throw new Error(`生成股是股非交易计划失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfTradePlan>;
}

export async function saveLatestGsgfReviewSnapshot(): Promise<GsgfReviewSnapshotResponse> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/review/snapshots/latest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`保存股是股非复盘快照失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfReviewSnapshotResponse>;
}

export async function recheckGsgfReview({
  windows = [1, 3, 5, 10],
  count = 180,
}: {
  windows?: number[];
  count?: number;
} = {}): Promise<GsgfReviewSummary> {
  const response = await fetch(`${API_BASE_URL}/api/gsgf/review/recheck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ windows, count }),
  });
  if (!response.ok) {
    throw new Error(`复查股是股非信号失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfReviewSummary>;
}

export async function createIntradaySnapshot({
  gsgfContext = {},
  limit = 30,
  watchlistText = "",
  useWatchlistPool = false,
}: {
  gsgfContext?: Record<string, { final_status?: string; confirm_type?: string | null; setup_type?: string | null; risk_flags?: string[] }>;
  limit?: number;
  watchlistText?: string;
  useWatchlistPool?: boolean;
} = {}): Promise<StrongStockIntradaySnapshot> {
  const response = await fetch(`${API_BASE_URL}/api/intraday/snapshot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      gsgf_context: gsgfContext,
      limit,
      watchlist_text: watchlistText,
      use_watchlist_pool: useWatchlistPool,
    }),
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const payload = JSON.parse(detail) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep raw response text.
    }
    throw new Error(`运行盘中监控失败：${response.status} ${detail}`);
  }
  return response.json() as Promise<StrongStockIntradaySnapshot>;
}

export async function getWatchlistPool(): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool`);
  if (!response.ok) {
    throw new Error(`读取自选股股票池失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function saveWatchlistPool(content: string): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error(`保存自选股股票池失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function addWatchlistPoolItem(item: WatchlistPoolItemRequest): Promise<WatchlistPoolResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/pool/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
  if (!response.ok) {
    throw new Error(`加入自选股失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistPoolResponse>;
}

export async function getWatchlistGsgfStatus(): Promise<WatchlistGsgfStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/gsgf-status`);
  if (!response.ok) {
    throw new Error(`读取自选股结构触发失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<WatchlistGsgfStatusResponse>;
}

export async function getStockKline(symbol: string, count = 220): Promise<StockKlineResponse> {
  const response = await fetch(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/kline?count=${count}`);
  if (!response.ok) {
    throw new Error(`读取K线失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<StockKlineResponse>;
}

export async function getStockResearch(symbol: string): Promise<StockResearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/research`);
  if (!response.ok) {
    throw new Error(`读取个股研究失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<StockResearchResponse>;
}

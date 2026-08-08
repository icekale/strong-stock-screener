import type {
  AiAnalysisSettingsUpdate,
  AuctionModelTop3Response,
  AuctionReviewSummary,
  AuctionSnapshotResponse,
  AuctionTimelineResponse,
  AuctionTop3LiveConfirmationResponse,
  AuctionTop3PerformanceResponse,
  AuctionTop3TrainingGenerateResponse,
  AuctionTop3TrainingSettings,
  AuctionTop3TrainingSummary,
  BackgroundJobState,
  CapitalSummaryResponse,
  ChanlunAnalysisResponse,
  ChanlunAlertListResponse,
  ChanlunAlertRefreshResponse,
  ChanlunBackfillRequest,
  ChanlunBacktestResponse,
  ChanlunPaperAccount,
  ChanlunPaperOrder,
  ChanlunPeriod,
  ChanlunReplayResponse,
  ChanlunSymbolSearchResponse,
  ChanlunWorkspaceResponse,
  CzscResearchSnapshot,
  CzscShadowScreeningJobResponse,
  DataSourceStatusResponse,
  EtfActivityAlertResponse,
  EtfAlertReadResponse,
  EtfExcessFlowResponse,
  EtfPriceHistoryResponse,
  EtfRadarHistoryResponse,
  EtfRadarHoldersResponse,
  EtfRadarMethodologyResponse,
  EtfRadarOverviewResponse,
  EtfThreeFactorHistoryResponse,
  EtfThreeFactorResponse,
  GsgfAnalysis,
  GsgfAutoReviewConfig,
  GsgfBacktestSummary,
  GsgfModelHealth,
  GsgfRealCalibrationSummary,
  GsgfReviewSnapshotResponse,
  GsgfReviewSummary,
  GsgfTradePlan,
  HeatmapMarketKey,
  HeatmapOverviewResponse,
  HeatmapPeriodKey,
  HeatmapQuotesResponse,
  HeatmapTreemapResponse,
  MarketEmotionSnapshotResponse,
  MarketOverviewResponse,
  MarketRankingsResponse,
  ModelMaintenancePacket,
  ModelMaintenanceReport,
  ModelMaintenanceSuggestion,
  NotificationChannelConfig,
  NotificationSendResult,
  PlateRotationReferenceResponse,
  PlateRotationSource,
  RuntimeSettingsHealthResponse,
  RuntimeSettingsResponse,
  ScreenRunFilters,
  ScreenRunJobState,
  ScreenStrategy,
  SectorReplicaMode,
  SectorReplicaRadarResponse,
  SectorReplicaStocksResponse,
  SectorRadarResponse,
  SectorWorkbenchMode,
  SectorWorkbenchResponse,
  SectorWorkbenchScopeRequest,
  SectorWorkbenchStatusResponse,
  SentimentDetailResponse,
  SentimentDecisionResponse,
  SentimentPercentileAnalysisResponse,
  SentimentPercentileResponse,
  SentimentWatchlistAlertsResponse,
  SentimentSummaryResponse,
  SentimentMonitorConfig,
  SentimentMonitorStatus,
  ShortTermIntradaySentimentResponse,
  ShortTermIntradaySignalDigest,
  ShortTermSentimentResponse,
  StockKlinePeriod,
  StockKlineResponse,
  StockQuoteResponse,
  StockResearchResponse,
  StrongStockIntradaySnapshot,
  StrongStockScreeningResponse,
  SystemCacheClearResponse,
  SystemCacheSummary,
  SystemStatusResponse,
  WatchlistGsgfStatusResponse,
  WatchlistPoolItemRequest,
  WatchlistPoolResponse,
} from "./types";
import { apiFetch } from "./product-request";

async function apiGet<T>(path: string, errorMessage: string): Promise<T> {
  const response = await apiFetch(path);
  if (!response.ok) {
    throw new Error(`${errorMessage}：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function apiSend<T>(path: string, errorMessage: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    throw new Error(`${errorMessage}：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

function defaultApiBaseUrl(): string {
  if (import.meta.env.MODE === "prod") {
    return "";
  }

  if (typeof window !== "undefined" && window.location.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8010`;
  }
  return "http://localhost:8010";
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl();

export class AuctionModelTop3CacheMissError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuctionModelTop3CacheMissError";
  }
}

export function isAuctionModelTop3CacheMiss(error: unknown): error is AuctionModelTop3CacheMissError {
  return error instanceof AuctionModelTop3CacheMissError;
}

export async function getDataSourceStatus(): Promise<DataSourceStatusResponse> {
  return apiGet<DataSourceStatusResponse>(`${API_BASE_URL}/api/data-sources/status`, "读取数据源状态失败");}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
  return apiGet<SystemStatusResponse>(`${API_BASE_URL}/api/system/status`, "读取系统状态失败");}

export async function getSystemCache(): Promise<SystemCacheSummary> {
  return apiGet<SystemCacheSummary>(`${API_BASE_URL}/api/system/cache`, "读取缓存状态失败");}

export async function clearSystemCache(group: string): Promise<SystemCacheClearResponse> {
  const trimmedGroup = group.trim();
  if (!trimmedGroup) {
    throw new Error("缓存分组不能为空");
  }
  const params = new URLSearchParams({ group: trimmedGroup });
  return apiSend<SystemCacheClearResponse>(`${API_BASE_URL}/api/system/cache/clear?${params.toString()}`, "清理缓存失败", {
    method: "POST",
  });}

export async function getMarketOverview(): Promise<MarketOverviewResponse> {
  return apiGet<MarketOverviewResponse>(`${API_BASE_URL}/api/market/overview`, "读取全A市场概览失败");}

export async function getCapitalSummary(): Promise<CapitalSummaryResponse> {
  return apiGet<CapitalSummaryResponse>(`${API_BASE_URL}/api/market/capital-summary`, "读取资金信号摘要失败");}

export async function getEtfRadarOverview(): Promise<EtfRadarOverviewResponse> {
  return apiGet<EtfRadarOverviewResponse>(`${API_BASE_URL}/api/etf-radar/overview`, "读取ETF资金雷达失败");}

export async function getEtfRadarHistory(days = 120): Promise<EtfRadarHistoryResponse> {
  const params = new URLSearchParams({ days: String(days) });
  return apiGet<EtfRadarHistoryResponse>(`${API_BASE_URL}/api/etf-radar/history?${params.toString()}`, "读取ETF份额历史失败");}

export async function getEtfPriceHistory(symbol: string, days = 120): Promise<EtfPriceHistoryResponse> {
  const params = new URLSearchParams({ days: String(days) });
  return apiGet<EtfPriceHistoryResponse>(`${API_BASE_URL}/api/etf-radar/price-history/${encodeURIComponent(symbol)}?${params.toString()}`, "读取ETF收盘价历史失败");}

export async function getEtfExcessFlow(days = 60): Promise<EtfExcessFlowResponse> {
  const params = new URLSearchParams({ days: String(days) });
  return apiGet<EtfExcessFlowResponse>(`${API_BASE_URL}/api/etf-radar/excess-flow?${params.toString()}`, "读取ETF超量资金趋势失败");}

export async function getEtfRadarHolders(): Promise<EtfRadarHoldersResponse> {
  return apiGet<EtfRadarHoldersResponse>(`${API_BASE_URL}/api/etf-radar/holders`, "读取ETF持有人披露失败");}

export async function getEtfRadarMethodology(): Promise<EtfRadarMethodologyResponse> {
  return apiGet<EtfRadarMethodologyResponse>(`${API_BASE_URL}/api/etf-radar/methodology`, "读取ETF资金雷达方法失败");}

export async function getEtfThreeFactor(): Promise<EtfThreeFactorResponse> {
  return apiGet<EtfThreeFactorResponse>(`${API_BASE_URL}/api/etf-radar/three-factor`, "读取ETF三因子信号失败");}

export async function getEtfThreeFactorHistory(
  symbol: string,
  days = 40,
): Promise<EtfThreeFactorHistoryResponse> {
  const params = new URLSearchParams({ days: String(days) });
  return apiSend<EtfThreeFactorHistoryResponse>(`${API_BASE_URL}/api/etf-radar/three-factor/${encodeURIComponent(symbol)}/history?${params.toString()}`, "读取ETF三因子历史失败");}

export async function getEtfActivityAlerts(unreadOnly = false): Promise<EtfActivityAlertResponse> {
  const params = new URLSearchParams({ unread_only: String(unreadOnly) });
  return apiGet<EtfActivityAlertResponse>(`${API_BASE_URL}/api/etf-radar/alerts?${params.toString()}`, "读取ETF活动提醒失败");}

export async function markEtfAlertRead(alertId: string): Promise<EtfAlertReadResponse> {
  return apiSend<EtfAlertReadResponse>(`${API_BASE_URL}/api/etf-radar/alerts/${encodeURIComponent(alertId)}/read`, "标记ETF活动提醒已读失败", {
    method: "POST",
  });}

export async function markAllEtfAlertsRead(): Promise<EtfAlertReadResponse> {
  return apiSend<EtfAlertReadResponse>(`${API_BASE_URL}/api/etf-radar/alerts/read-all`, "标记全部ETF活动提醒已读失败", { method: "POST" });}

export async function getMarketRankings(limit = 30): Promise<MarketRankingsResponse> {
  return apiGet<MarketRankingsResponse>(`${API_BASE_URL}/api/market/rankings?limit=${encodeURIComponent(limit)}`, "读取全A实时排行榜失败");}

export async function getHeatmapTreemap(query: URLSearchParams): Promise<HeatmapTreemapResponse> {
  return apiGet<HeatmapTreemapResponse>(`${API_BASE_URL}/api/heatmap/treemap?${query.toString()}`, "读取市场热图失败");}

export async function getHeatmapQuotes(
  market: HeatmapMarketKey,
  period: HeatmapPeriodKey,
): Promise<HeatmapQuotesResponse> {
  const params = new URLSearchParams({ market, period });
  return apiGet<HeatmapQuotesResponse>(`${API_BASE_URL}/api/heatmap/quotes?${params.toString()}`, "读取热图行情失败");}

export async function getHeatmapOverview(period: HeatmapPeriodKey): Promise<HeatmapOverviewResponse> {
  const params = new URLSearchParams({ period });
  return apiGet<HeatmapOverviewResponse>(`${API_BASE_URL}/api/heatmap/overview?${params.toString()}`, "读取热图概览失败");}

export async function getAuctionLatest(limit = 100): Promise<AuctionSnapshotResponse> {
  return apiGet<AuctionSnapshotResponse>(`${API_BASE_URL}/api/auction/latest?limit=${encodeURIComponent(limit)}`, "读取竞价雷达快照失败");}

export async function getAuctionSnapshot(limit = 100, refresh = false): Promise<AuctionSnapshotResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    refresh: String(refresh),
  });
  return apiGet<AuctionSnapshotResponse>(`${API_BASE_URL}/api/auction/snapshot?${params.toString()}`, "读取竞价雷达失败");}

export async function createAuctionSnapshotJob(limit = 100): Promise<BackgroundJobState> {
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/auction/snapshot/jobs?limit=${encodeURIComponent(limit)}`, "启动竞价刷新任务失败", {
    method: "POST",
  });}

export async function getAuctionSnapshotJob(jobId: string): Promise<BackgroundJobState> {
  return apiGet<BackgroundJobState>(`${API_BASE_URL}/api/auction/snapshot/jobs/${encodeURIComponent(jobId)}`, "读取竞价刷新任务失败");}

export async function getAuctionTimeline(limit = 8): Promise<AuctionTimelineResponse> {
  return apiGet<AuctionTimelineResponse>(`${API_BASE_URL}/api/auction/timeline?limit=${encodeURIComponent(limit)}`, "读取竞价时间轴失败");}

export async function getAuctionModelTop3(
  tradeDate: string,
  options: { cacheOnly?: boolean; refresh?: boolean } = {},
): Promise<AuctionModelTop3Response> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  if (options.cacheOnly) {
    params.set("cache_only", "true");
  }
  if (options.refresh) {
    params.set("refresh", "true");
  }
  const response = await apiFetch(`${API_BASE_URL}/api/auction/model/top3?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.text();
    if (options.cacheOnly && response.status === 404) {
      throw new AuctionModelTop3CacheMissError(detail);
    }
    throw new Error(`读取竞价模型Top3失败：${response.status} ${detail}`);
  }
  return response.json() as Promise<AuctionModelTop3Response>;
}

export async function createAuctionModelTop3Job(tradeDate: string): Promise<BackgroundJobState> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/auction/model/top3/jobs?${params.toString()}`, "启动竞价模型Top3生成任务失败", {
    method: "POST",
  });}

export async function getAuctionModelTop3Job(jobId: string): Promise<BackgroundJobState> {
  return apiGet<BackgroundJobState>(`${API_BASE_URL}/api/auction/model/top3/jobs/${encodeURIComponent(jobId)}`, "读取竞价模型Top3生成任务失败");}

export async function getAuctionModelLiveConfirmation(tradeDate: string): Promise<AuctionTop3LiveConfirmationResponse> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  return apiGet<AuctionTop3LiveConfirmationResponse>(`${API_BASE_URL}/api/auction/model/top3/live-confirmation?${params.toString()}`, "读取竞价模型Top3实盘确认失败");}

export async function getAuctionReviewLatest(): Promise<AuctionReviewSummary> {
  return apiGet<AuctionReviewSummary>(`${API_BASE_URL}/api/auction/review/latest`, "读取竞价复盘失败");}

export async function getAuctionReview(tradeDate?: string, limit = 100): Promise<AuctionReviewSummary> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (tradeDate) {
    params.set("trade_date", tradeDate);
  }
  return apiGet<AuctionReviewSummary>(`${API_BASE_URL}/api/auction/review?${params.toString()}`, "读取竞价复盘记录失败");}

export async function finalizeAuctionReview(tradeDate: string): Promise<AuctionReviewSummary> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  return apiSend<AuctionReviewSummary>(`${API_BASE_URL}/api/auction/review/finalize?${params.toString()}`, "生成竞价复盘失败", {
    method: "POST",
  });}

export async function getAuctionRuleSummary(limit = 2000): Promise<AuctionReviewSummary> {
  return apiGet<AuctionReviewSummary>(`${API_BASE_URL}/api/auction/rules/summary?limit=${encodeURIComponent(limit)}`, "读取竞价规则统计失败");}

export async function getSectorRadar(limit = 20): Promise<SectorRadarResponse> {
  return apiGet<SectorRadarResponse>(`${API_BASE_URL}/api/sectors/radar?limit=${encodeURIComponent(limit)}`, "读取板块资金流失败");}

export async function getSectorWorkbench(
  options: {
    mode?: SectorWorkbenchMode;
    scope?: SectorWorkbenchScopeRequest;
    selected?: string[];
    limit?: number;
    stockLimit?: number;
  } = {},
): Promise<SectorWorkbenchResponse> {
  const params = new URLSearchParams();
  if (options.mode) {
    params.set("mode", options.mode);
  }
  if (options.scope) {
    params.set("scope", options.scope);
  }
  if (options.selected?.length) {
    params.set("selected", options.selected.join(","));
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.stockLimit) {
    params.set("stock_limit", String(options.stockLimit));
  }
  const suffix = params.toString();
  return apiGet<SectorWorkbenchResponse>(`${API_BASE_URL}/api/sectors/workbench${suffix ? `?${suffix}` : ""}`, "读取题材工作台失败");}

export async function getSectorWorkbenchStatus(tradeDate?: string | null): Promise<SectorWorkbenchStatusResponse> {
  const params = new URLSearchParams();
  if (tradeDate) {
    params.set("trade_date", tradeDate);
  }
  const suffix = params.toString();
  return apiGet<SectorWorkbenchStatusResponse>(`${API_BASE_URL}/api/sectors/workbench/status${suffix ? `?${suffix}` : ""}`, "读取板块采样状态失败");}

export async function getSectorReplicaRadar(
  options: {
    mode?: SectorReplicaMode;
    selected?: string[];
    limit?: number;
    stockLimit?: number;
  } = {},
): Promise<SectorReplicaRadarResponse> {
  const params = new URLSearchParams();
  if (options.mode) {
    params.set("mode", options.mode);
  }
  if (options.selected?.length) {
    params.set("selected", options.selected.join(","));
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.stockLimit) {
    params.set("stock_limit", String(options.stockLimit));
  }
  const suffix = params.toString();
  return apiGet<SectorReplicaRadarResponse>(`${API_BASE_URL}/api/sectors/replica/radar${suffix ? `?${suffix}` : ""}`, "读取短线侠兼容板块雷达失败");}

export async function getSectorReplicaBoardStocks(
  boardCode: string,
  options: {
    boardName?: string | null;
    mode?: SectorReplicaMode;
    subTheme?: string | null;
    limit?: number;
  } = {},
): Promise<SectorReplicaStocksResponse> {
  const params = new URLSearchParams();
  if (options.boardName) {
    params.set("board_name", options.boardName);
  }
  if (options.mode) {
    params.set("mode", options.mode);
  }
  if (options.subTheme) {
    params.set("sub_theme", options.subTheme);
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  const suffix = params.toString();
  return apiSend<SectorReplicaStocksResponse>(`${API_BASE_URL}/api/sectors/replica/boards/${encodeURIComponent(boardCode)}/stocks${suffix ? `?${suffix}` : ""}`, "读取板块成分股失败");}

export async function getPlateRotationReference(
  limit = 10,
  source: PlateRotationSource = "kaipan",
  days = 20,
): Promise<PlateRotationReferenceResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    source,
    days: String(days),
  });
  return apiGet<PlateRotationReferenceResponse>(`${API_BASE_URL}/api/sectors/plate-reference?${params.toString()}`, "读取短线题材参考榜失败");}

export async function getShortTermSentiment(tradeDate: string, limit = 50): Promise<ShortTermSentimentResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
  });
  return apiGet<ShortTermSentimentResponse>(`${API_BASE_URL}/api/short-term/sentiment?${params.toString()}`, "读取短线情绪失败");}

export async function getMarketSentimentPercentile(
  asOf?: string,
  refresh = false,
): Promise<SentimentPercentileResponse> {
  const params = new URLSearchParams({ refresh: String(refresh) });
  if (asOf) params.set("as_of", asOf);
  return apiGet<SentimentPercentileResponse>(`${API_BASE_URL}/api/short-term/sentiment/percentile?${params.toString()}`, "读取市场情绪百分位失败");}

export async function getMarketSentimentAnalysis(
  tradeDate: string,
): Promise<SentimentPercentileAnalysisResponse> {
  const params = new URLSearchParams({ trade_date: tradeDate });
  return apiGet<SentimentPercentileAnalysisResponse>(`${API_BASE_URL}/api/short-term/sentiment/percentile/analysis?${params.toString()}`, "读取市场情绪解读失败");}

export async function generateMarketSentimentAnalysis(
  tradeDate: string,
  force = false,
): Promise<SentimentPercentileAnalysisResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    force: String(force),
  });
  return apiSend<SentimentPercentileAnalysisResponse>(`${API_BASE_URL}/api/short-term/sentiment/percentile/analysis/generate?${params.toString()}`, "生成市场情绪解读失败", { method: "POST" },);}

export async function getSentimentDecision(
  tradeDate: string,
  limit = 80,
  refresh = false,
): Promise<SentimentDecisionResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    refresh: String(refresh),
  });
  return apiGet<SentimentDecisionResponse>(`${API_BASE_URL}/api/short-term/sentiment/decision?${params.toString()}`, "读取情绪交易许可失败");}

export async function archiveSentimentDecision(tradeDate: string, limit = 80): Promise<SentimentDecisionResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
  });
  return apiSend<SentimentDecisionResponse>(`${API_BASE_URL}/api/short-term/sentiment/review/archive?${params.toString()}`, "归档情绪结论失败", {
    method: "POST",
  });}

export async function getSentimentWatchlistAlerts(
  tradeDate: string,
  limit = 80,
  refresh = false,
): Promise<SentimentWatchlistAlertsResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    limit: String(limit),
    refresh: String(refresh),
  });
  return apiGet<SentimentWatchlistAlertsResponse>(`${API_BASE_URL}/api/short-term/sentiment/watchlist-alerts?${params.toString()}`, "读取自选股情绪联动失败");}

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
  return apiGet<SentimentSummaryResponse>(`${API_BASE_URL}/api/short-term/sentiment/summary?${params.toString()}`, "读取短线情绪概览失败");}

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
  return apiGet<SentimentDetailResponse>(`${API_BASE_URL}/api/short-term/sentiment/detail?${params.toString()}`, "读取短线情绪详情失败");}

export async function getMarketEmotionSnapshot(
  tradeDate: string,
  limit = 80,
  includeDistribution = true,
): Promise<MarketEmotionSnapshotResponse> {
  const params = new URLSearchParams({
    trade_date: tradeDate,
    include_distribution: String(includeDistribution),
    limit: String(limit),
  });
  return apiGet<MarketEmotionSnapshotResponse>(`${API_BASE_URL}/api/short-term/market-emotion?${params.toString()}`, "读取市场情绪仪表盘失败");}

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
  return apiGet<ShortTermIntradaySentimentResponse>(`${API_BASE_URL}/api/short-term/sentiment/intraday?${params.toString()}`, "读取盘中情绪失败");}

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
  return apiGet<ShortTermIntradaySignalDigest>(`${API_BASE_URL}/api/short-term/sentiment/intraday/digest?${params.toString()}`, "生成短线提醒草稿失败");}

export async function getSentimentMonitorStatus(): Promise<SentimentMonitorStatus> {
  return apiGet<SentimentMonitorStatus>(`${API_BASE_URL}/api/short-term/sentiment/monitor/status`, "读取后台监控状态失败");}

export async function saveSentimentMonitorConfig(
  payload: SentimentMonitorConfig,
): Promise<SentimentMonitorStatus> {
  return apiSend<SentimentMonitorStatus>(`${API_BASE_URL}/api/short-term/sentiment/monitor/config`, "保存后台监控配置失败", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });}

export async function startSentimentMonitor(): Promise<SentimentMonitorStatus> {
  return apiSend<SentimentMonitorStatus>(`${API_BASE_URL}/api/short-term/sentiment/monitor/start`, "启动后台监控失败", {
    method: "POST",
  });}

export async function stopSentimentMonitor(): Promise<SentimentMonitorStatus> {
  return apiSend<SentimentMonitorStatus>(`${API_BASE_URL}/api/short-term/sentiment/monitor/stop`, "停止后台监控失败", {
    method: "POST",
  });}

export async function runSentimentMonitorOnce(tradeDate?: string): Promise<SentimentMonitorStatus> {
  const suffix = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : "";
  return apiSend<SentimentMonitorStatus>(`${API_BASE_URL}/api/short-term/sentiment/monitor/run-once${suffix}`, "手动采样失败", {
    method: "POST",
  });}

export async function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  return apiGet<RuntimeSettingsResponse>(`${API_BASE_URL}/api/settings`, "读取设置失败");}

export async function saveRuntimeSettings(payload: {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow" | "eastmoney";
  quote_provider: "tickflow" | "eastmoney";
  tickflow_api_key?: string | null;
  tickflow_base_url: string;
  ifind_api_key?: string | null;
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  tdx_api_key?: string | null;
  tdx_base_url: string;
  provider_timeout_seconds: number;
  notification_channels?: NotificationChannelConfig[];
  sentiment_monitor?: SentimentMonitorConfig;
  gsgf_auto_review?: GsgfAutoReviewConfig;
  ai_analysis?: AiAnalysisSettingsUpdate;
  auction_top3_training?: AuctionTop3TrainingSettings;
}): Promise<RuntimeSettingsResponse> {
  return apiSend<RuntimeSettingsResponse>(`${API_BASE_URL}/api/settings`, "保存设置失败", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });}

export async function sendNotificationMessage(payload: {
  title: string;
  message_text: string;
  channel_ids?: string[];
}): Promise<NotificationSendResult> {
  return apiSend<NotificationSendResult>(`${API_BASE_URL}/api/notifications/send`, "发送通知失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });}

export async function checkRuntimeSettingsHealth(symbol = "605289.SH"): Promise<RuntimeSettingsHealthResponse> {
  return apiGet<RuntimeSettingsHealthResponse>(`${API_BASE_URL}/api/settings/health?symbol=${encodeURIComponent(symbol)}`, "健康检查失败");}

export async function createScreenRun(
  tradeDate: string,
  limit = 30,
  scanLimit = 160,
  filters: ScreenRunFilters = {},
  options: {
    strategy?: ScreenStrategy;
    include_gsgf?: boolean;
    exclude_gsgf_hard_risk?: boolean;
  } = {},
): Promise<StrongStockScreeningResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/screen/runs`, {
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

export async function createScreenRunJob(
  tradeDate: string,
  limit = 30,
  scanLimit = 160,
  filters: ScreenRunFilters = {},
  options: {
    strategy?: ScreenStrategy;
    include_gsgf?: boolean;
    exclude_gsgf_hard_risk?: boolean;
  } = {},
): Promise<ScreenRunJobState> {
  return apiSend<ScreenRunJobState>(`${API_BASE_URL}/api/screen/runs/jobs`, "启动筛选任务失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trade_date: tradeDate, limit, scan_limit: scanLimit, filters, ...options }),
  });}

export async function getScreenRunJob(jobId: string): Promise<ScreenRunJobState> {
  return apiGet<ScreenRunJobState>(`${API_BASE_URL}/api/screen/runs/jobs/${encodeURIComponent(jobId)}`, "读取筛选任务失败");}

export async function getCzscShadowScreeningJob(jobId: string): Promise<CzscShadowScreeningJobResponse> {
  return apiSend<CzscShadowScreeningJobResponse>(`${API_BASE_URL}/api/chanlun/screening/shadow/jobs/${encodeURIComponent(jobId)}`, "读取CZSC研究任务失败");}

export async function getLatestScreenRun(): Promise<StrongStockScreeningResponse> {
  return apiGet<StrongStockScreeningResponse>(`${API_BASE_URL}/api/screen/runs/latest`, "读取最近筛选失败");}

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
  return apiSend<GsgfBacktestSummary>(`${API_BASE_URL}/api/gsgf/backtest`, "运行股是股非回测失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbols,
      windows,
      min_history: minHistory,
      count,
    }),
  });}

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
  return apiSend<GsgfRealCalibrationSummary>(`${API_BASE_URL}/api/gsgf/calibration`, "运行股是股非真实样本校准失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trade_dates: tradeDates,
      windows,
      scan_limit: scanLimit,
      count,
    }),
  });}

export async function getLatestGsgfReview(): Promise<GsgfReviewSummary | null> {
  const response = await apiFetch(`${API_BASE_URL}/api/gsgf/review/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`读取最新股是股非复盘失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfReviewSummary>;
}

export async function createGsgfCalibrationJob({
  tradeDates,
  windows = [1, 3, 5, 10],
  scanLimit = 80,
  count = 260,
}: {
  tradeDates: string[];
  windows?: number[];
  scanLimit?: number;
  count?: number;
}): Promise<BackgroundJobState> {
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/gsgf/calibration/jobs`, "启动股是股非校准任务失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trade_dates: tradeDates,
      windows,
      scan_limit: scanLimit,
      count,
    }),
  });}

export async function getGsgfCalibrationJob(jobId: string): Promise<BackgroundJobState> {
  return apiGet<BackgroundJobState>(`${API_BASE_URL}/api/gsgf/calibration/jobs/${encodeURIComponent(jobId)}`, "读取股是股非校准任务失败");}

export async function cancelGsgfCalibrationJob(jobId: string): Promise<BackgroundJobState> {
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/gsgf/calibration/jobs/${encodeURIComponent(jobId)}/cancel`, "取消股是股非校准任务失败", {
    method: "POST",
  });}

export async function getLatestGsgfCalibration(): Promise<GsgfRealCalibrationSummary | null> {
  const response = await apiFetch(`${API_BASE_URL}/api/gsgf/calibration/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`读取最新股是股非校准失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<GsgfRealCalibrationSummary>;
}

export async function getGsgfModelHealth(): Promise<GsgfModelHealth> {
  return apiGet<GsgfModelHealth>(`${API_BASE_URL}/api/gsgf/health`, "读取股是股非模型健康失败");}

export async function generateModelMaintenancePacket(): Promise<ModelMaintenancePacket> {
  return apiSend<ModelMaintenancePacket>(`${API_BASE_URL}/api/model-maintenance/packets/generate`, "生成模型维护复盘包失败", { method: "POST" });}

export async function getLatestModelMaintenancePacket(): Promise<ModelMaintenancePacket | null> {
  const response = await apiFetch(`${API_BASE_URL}/api/model-maintenance/packets/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`读取模型维护数据包失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenancePacket>;
}

export async function getModelMaintenancePacket(packetId: string): Promise<ModelMaintenancePacket> {
  return apiGet<ModelMaintenancePacket>(`${API_BASE_URL}/api/model-maintenance/packets/${encodeURIComponent(packetId)}`, "读取模型维护数据包失败");}

export async function getLatestModelMaintenanceReport(): Promise<ModelMaintenanceReport | null> {
  const response = await apiFetch(`${API_BASE_URL}/api/model-maintenance/reports/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`读取模型维护报告失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ModelMaintenanceReport>;
}

export async function getAuctionTop3TrainingSummary(): Promise<AuctionTop3TrainingSummary> {
  return apiGet<AuctionTop3TrainingSummary>(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/summary`, "读取竞价 Top3 训练摘要失败");}

export async function getAuctionTop3TrainingPerformance(): Promise<AuctionTop3PerformanceResponse> {
  return apiGet<AuctionTop3PerformanceResponse>(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/performance`, "读取竞价 Top3 模拟收益失败");}

export async function generateAuctionTop3TrainingSamples(
  tradeDate?: string,
): Promise<AuctionTop3TrainingGenerateResponse> {
  const suffix = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : "";
  return apiSend<AuctionTop3TrainingGenerateResponse>(`${API_BASE_URL}/api/model-maintenance/auction-top3/training/generate${suffix}`, "生成竞价 Top3 训练样本失败", {
    method: "POST",
  });}

export async function analyzeModelMaintenance(): Promise<ModelMaintenanceReport> {
  return apiSend<ModelMaintenanceReport>(`${API_BASE_URL}/api/model-maintenance/analyze`, "生成模型维护 AI 分析失败", { method: "POST" });}

export async function updateModelMaintenanceSuggestion(
  suggestionId: string,
  action: "accept" | "ignore" | "snooze",
): Promise<ModelMaintenanceSuggestion> {
  return apiSend<ModelMaintenanceSuggestion>(`${API_BASE_URL}/api/model-maintenance/suggestions/${encodeURIComponent(suggestionId)}/${action}`, "更新模型维护建议失败", { method: "POST" },);}

export async function buildGsgfTradePlan(analysis: GsgfAnalysis): Promise<GsgfTradePlan> {
  return apiSend<GsgfTradePlan>(`${API_BASE_URL}/api/gsgf/trade-plan`, "生成股是股非交易计划失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis }),
  });}

export async function saveLatestGsgfReviewSnapshot(): Promise<GsgfReviewSnapshotResponse> {
  return apiSend<GsgfReviewSnapshotResponse>(`${API_BASE_URL}/api/gsgf/review/snapshots/latest`, "保存股是股非复盘快照失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });}

export async function recheckGsgfReview({
  windows = [1, 3, 5, 10],
  count = 180,
}: {
  windows?: number[];
  count?: number;
} = {}): Promise<GsgfReviewSummary> {
  return apiSend<GsgfReviewSummary>(`${API_BASE_URL}/api/gsgf/review/recheck`, "复查股是股非信号失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ windows, count }),
  });}

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
  const response = await apiFetch(`${API_BASE_URL}/api/intraday/snapshot`, {
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
  return apiGet<WatchlistPoolResponse>(`${API_BASE_URL}/api/watchlist/pool`, "读取自选股股票池失败");}

export async function saveWatchlistPool(content: string): Promise<WatchlistPoolResponse> {
  return apiSend<WatchlistPoolResponse>(`${API_BASE_URL}/api/watchlist/pool`, "保存自选股股票池失败", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });}

export async function addWatchlistPoolItem(item: WatchlistPoolItemRequest): Promise<WatchlistPoolResponse> {
  return apiSend<WatchlistPoolResponse>(`${API_BASE_URL}/api/watchlist/pool/items`, "加入自选股失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });}

export async function getWatchlistGsgfStatus(): Promise<WatchlistGsgfStatusResponse> {
  return apiGet<WatchlistGsgfStatusResponse>(`${API_BASE_URL}/api/watchlist/gsgf-status`, "读取自选股结构触发失败");}

export async function getStockKline(
  symbol: string,
  optionsOrCount: { count?: number; period?: StockKlinePeriod } | number = {},
): Promise<StockKlineResponse> {
  const options = typeof optionsOrCount === "number" ? { count: optionsOrCount } : optionsOrCount;
  const params = new URLSearchParams({ count: String(options.count ?? 220) });
  if (typeof optionsOrCount !== "number" || options.period) {
    params.set("period", options.period ?? "1d");
  }
  return apiSend<StockKlineResponse>(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/kline?${params.toString()}`, "读取K线失败");}

export async function getStockQuote(symbol: string): Promise<StockQuoteResponse> {
  return apiGet<StockQuoteResponse>(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/quote`, "读取实时行情失败");}

export async function getStockResearch(symbol: string): Promise<StockResearchResponse> {
  return apiGet<StockResearchResponse>(`${API_BASE_URL}/api/stocks/${encodeURIComponent(symbol)}/research`, "读取个股研究失败");}

export async function getChanlunAnalysis(
  symbol: string,
  options: {
    period?: ChanlunPeriod;
    lookback?: number;
    includeObserving?: boolean;
  } = {},
): Promise<ChanlunAnalysisResponse> {
  const params = new URLSearchParams({
    period: options.period ?? "1d",
    lookback: String(options.lookback ?? 220),
    include_observing: String(options.includeObserving ?? false),
  });
  return apiSend<ChanlunAnalysisResponse>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/analysis?${params.toString()}`, "读取缠论分析失败");}

export async function getCzscResearchSignals(
  symbol: string,
  options: { lookback?: number } = {},
): Promise<CzscResearchSnapshot> {
  const params = new URLSearchParams({ lookback: String(options.lookback ?? 220) });
  return apiSend<CzscResearchSnapshot>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/research-signals?${params.toString()}`, "读取缠论研究信号失败");}

export async function getChanlunWorkspace(
  symbol: string,
  options: { lookback?: number } = {},
): Promise<ChanlunWorkspaceResponse> {
  const params = new URLSearchParams({ lookback: String(options.lookback ?? 220) });
  return apiSend<ChanlunWorkspaceResponse>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/workspace?${params.toString()}`, "读取缠论工作台失败");}

export async function getChanlunReplay(
  symbol: string,
  options: { period?: ChanlunPeriod; lookback?: number } = {},
): Promise<ChanlunReplayResponse> {
  const params = new URLSearchParams({
    period: options.period ?? "1d",
    lookback: String(options.lookback ?? 220),
  });
  return apiSend<ChanlunReplayResponse>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/replays?${params.toString()}`, "读取缠论历史回放失败");}

export async function getChanlunBacktest(
  symbol: string,
  options: { period?: ChanlunPeriod; lookback?: number; horizons?: number[] } = {},
): Promise<ChanlunBacktestResponse> {
  const params = new URLSearchParams({
    period: options.period ?? "1d",
    lookback: String(options.lookback ?? 220),
  });
  if (options.horizons?.length) {
    params.set("horizons", options.horizons.join(","));
  }
  return apiSend<ChanlunBacktestResponse>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/backtests?${params.toString()}`, "读取缠论绩效回测失败");}

export async function getChanlunAlerts(
  options: { symbol?: string; limit?: number } = {},
): Promise<ChanlunAlertListResponse> {
  const params = new URLSearchParams({ limit: String(options.limit ?? 100) });
  if (options.symbol) {
    params.set("symbol", options.symbol);
  }
  return apiGet<ChanlunAlertListResponse>(`${API_BASE_URL}/api/chanlun/alerts?${params.toString()}`, "读取缠论预警失败");}

export async function refreshChanlunAlerts(
  symbol: string,
  options: { period?: ChanlunPeriod; lookback?: number } = {},
): Promise<ChanlunAlertRefreshResponse> {
  const params = new URLSearchParams({
    period: options.period ?? "1d",
    lookback: String(options.lookback ?? 220),
  });
  return apiSend<ChanlunAlertRefreshResponse>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/alerts/refresh?${params.toString()}`, "刷新缠论预警失败", { method: "POST" },);}

export async function createChanlunPaperOrderDraft(
  symbol: string,
  options: { quantity?: number; lookback?: number } = {},
): Promise<ChanlunPaperOrder> {
  const params = new URLSearchParams({ lookback: String(options.lookback ?? 220) });
  return apiSend<ChanlunPaperOrder>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/paper-orders/drafts?${params.toString()}`, "创建缠论模拟订单草案失败", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantity: options.quantity ?? 100 }),
    },);}

export async function approveChanlunPaperOrder(orderId: string): Promise<ChanlunPaperOrder> {
  return apiSend<ChanlunPaperOrder>(`${API_BASE_URL}/api/chanlun/paper-orders/${encodeURIComponent(orderId)}/approve`, "确认缠论模拟订单失败", {
    method: "POST",
  });}

export async function cancelChanlunPaperOrder(orderId: string): Promise<ChanlunPaperOrder> {
  return apiSend<ChanlunPaperOrder>(`${API_BASE_URL}/api/chanlun/paper-orders/${encodeURIComponent(orderId)}/cancel`, "撤销缠论模拟订单失败", {
    method: "POST",
  });}

export async function fillChanlunPaperOrder(orderId: string): Promise<ChanlunPaperOrder> {
  return apiSend<ChanlunPaperOrder>(`${API_BASE_URL}/api/chanlun/paper-orders/${encodeURIComponent(orderId)}/fill`, "更新缠论模拟成交失败", {
    method: "POST",
  });}

export async function getChanlunPaperAccount(): Promise<ChanlunPaperAccount> {
  return apiGet<ChanlunPaperAccount>(`${API_BASE_URL}/api/chanlun/paper-account`, "读取缠论模拟账户失败");}

export async function searchStockSymbols(
  query: string,
  options: { limit?: number } = {},
): Promise<ChanlunSymbolSearchResponse> {
  const params = new URLSearchParams({
    query,
    limit: String(options.limit ?? 20),
  });
  return apiGet<ChanlunSymbolSearchResponse>(`${API_BASE_URL}/api/chanlun/symbols/search?${params.toString()}`, "搜索股票失败");}

export const searchChanlunSymbols = searchStockSymbols;

export async function createChanlunBackfillJob(
  symbol: string,
  request: ChanlunBackfillRequest = {},
): Promise<BackgroundJobState> {
  const payload: ChanlunBackfillRequest = {
    periods: request.periods ?? ["5m", "30m", "60m"],
    lookback: request.lookback ?? 220,
    ...(request.history_days === undefined ? {} : { history_days: request.history_days }),
  };
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/backfill`, "启动缠论历史补齐失败", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });}

export async function getChanlunBackfillJob(
  symbol: string,
  jobId: string,
): Promise<BackgroundJobState> {
  return apiSend<BackgroundJobState>(`${API_BASE_URL}/api/chanlun/stocks/${encodeURIComponent(symbol)}/backfill/${encodeURIComponent(jobId)}`, "读取缠论历史补齐任务失败");}

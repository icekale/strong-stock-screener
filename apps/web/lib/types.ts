export type SourceStatusValue = "success" | "failed" | "disabled" | "missing_key";
export type RiskCheckStatus = "triggered" | "clear" | "unknown";
export type ScreenStrategy = "strong_stock" | "gsgf" | "combined";
export type GsgfIntradayConfirmation = "盘中确认" | "等待确认" | "低吸确认" | "减仓确认" | "风险失效" | "无GSGF上下文";
export type GsgfAction = "strong_candidate" | "watch_candidate" | "wait_trigger" | "avoid";
export type GsgfFinalStatus = "确认买点" | "候选" | "低吸观察" | "观察" | "减仓" | "回避";
export type GsgfZone = "a_zone" | "b_zone_a_point" | "c_zone" | "unformed" | "unknown";
export type GsgfVolumeStructure =
  | "three_yang_controls_three_yin"
  | "neutral"
  | "three_yin_controls_three_yang"
  | "unknown";
export type GsgfChartAnnotationType = "volume_structure" | "zone" | "trigger" | "pressure" | "risk";
export type GsgfChartAnnotationSeverity = "positive" | "neutral" | "warning" | "danger";

export type GsgfAnalysis = {
  model_version: string;
  total_score: number;
  action: GsgfAction;
  final_status: GsgfFinalStatus;
  zone: GsgfZone;
  volume_structure: GsgfVolumeStructure;
  setup_type: string | null;
  setup_score: number;
  confirm_type: string | null;
  confirm_score: number;
  scores: {
    safety_pressure: number;
    volume_thickness: number;
    ma_alignment: number;
    pattern_space: number;
    star_trigger: number;
    sector_theme: number;
  };
  pattern_tags: string[];
  trigger_tags: string[];
  pressure_flags: string[];
  risk_flags: string[];
  explanation: string[];
  trade_plan: GsgfTradePlan | null;
};

export type GsgfChartAnnotation = {
  type: GsgfChartAnnotationType;
  label: string;
  description: string;
  severity: GsgfChartAnnotationSeverity;
  date: string | null;
  start_date: string | null;
  end_date: string | null;
  price: number | null;
};

export type GsgfBacktestWindowStat = {
  window_days: number;
  sample_count: number;
  win_rate: number | null;
  avg_return_pct: number | null;
  median_return_pct: number | null;
  avg_max_drawdown_pct: number | null;
};

export type GsgfBacktestBucket = {
  status: GsgfFinalStatus;
  sample_count: number;
  avg_score: number | null;
  windows: GsgfBacktestWindowStat[];
};

export type StrongStockSourceStatus = {
  source: string;
  status: SourceStatusValue;
  detail: string;
};

export type GsgfBacktestSummary = {
  windows: number[];
  sample_count: number;
  buckets: GsgfBacktestBucket[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type GsgfTradePlan = {
  status: GsgfFinalStatus;
  holder_guidance: string[];
  empty_position_guidance: string[];
  risk_invalidation: string[];
  research_note: string;
};

export type GsgfReviewRecord = {
  trade_date: string;
  symbol: string;
  name: string;
  signal_type: string;
  status: GsgfFinalStatus;
  score: number;
  setup_type: string | null;
  confirm_type: string | null;
};

export type GsgfReviewSnapshotResponse = {
  saved_count: number;
  records: GsgfReviewRecord[];
  generated_at: string;
};

export type GsgfReviewWindowResult = {
  window_days: number;
  realized_return_pct: number | null;
  max_drawdown_pct: number | null;
};

export type GsgfReviewItem = {
  record: GsgfReviewRecord;
  confirmed: boolean;
  windows: GsgfReviewWindowResult[];
};

export type GsgfReviewBucket = {
  signal_type: string;
  status: GsgfFinalStatus;
  sample_count: number;
  confirmed_count: number;
  avg_return_pct: number | null;
  avg_max_drawdown_pct: number | null;
};

export type GsgfReviewSummary = {
  windows: number[];
  record_count: number;
  items: GsgfReviewItem[];
  buckets: GsgfReviewBucket[];
  generated_at: string;
};

export type GsgfCalibrationExample = {
  trade_date: string;
  symbol: string;
  name: string;
  status: GsgfFinalStatus;
  score: number;
  setup_type: string | null;
  confirm_type: string | null;
  entry_close: number | null;
};

export type GsgfCalibrationWindowStat = {
  window_days: number;
  sample_count: number;
  hit_count: number;
  hit_rate: number | null;
  avg_return_pct: number | null;
  avg_max_drawdown_pct: number | null;
};

export type GsgfCalibrationSampleWindow = {
  window_days: number;
  realized_return_pct: number | null;
  max_drawdown_pct: number | null;
};

export type GsgfCalibrationSample = {
  trade_date: string;
  symbol: string;
  name: string;
  status: GsgfFinalStatus;
  score: number;
  setup_type: string | null;
  confirm_type: string | null;
  zone: GsgfZone;
  bucket_names: string[];
  entry_close: number | null;
  windows: GsgfCalibrationSampleWindow[];
};

export type GsgfCalibrationBucket = {
  name: string;
  sample_count: number;
  windows: GsgfCalibrationWindowStat[];
  examples: GsgfCalibrationExample[];
};

export type GsgfRealCalibrationSummary = {
  trade_dates: string[];
  windows: number[];
  scanned_count: number;
  target_sample_count: number;
  skipped_count: number;
  buckets: GsgfCalibrationBucket[];
  unique_symbol_buckets: GsgfCalibrationBucket[];
  samples: GsgfCalibrationSample[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type DataSourceStatusResponse = {
  items: StrongStockSourceStatus[];
};

export type MarketTurnoverSummary = {
  total_cny: number | null;
  previous_total_cny: number | null;
  change_cny: number | null;
  change_pct: number | null;
};

export type MarketAdvanceDeclineSummary = {
  advance_count: number | null;
  decline_count: number | null;
  unchanged_count: number | null;
  limit_up_count: number | null;
  limit_down_count: number | null;
};

export type MarketSectorStrengthItem = {
  name: string;
  change_pct: number | null;
  turnover_cny: number | null;
  advance_count: number | null;
  decline_count: number | null;
  leader: string | null;
  source: string;
};

export type MarketOverviewResponse = {
  trade_date: string | null;
  turnover: MarketTurnoverSummary;
  advance_decline: MarketAdvanceDeclineSummary;
  sectors: MarketSectorStrengthItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type SectorRadarItem = {
  name: string;
  source: string;
  change_pct: number | null;
  turnover_cny: number | null;
  advance_count: number | null;
  decline_count: number | null;
  leader: string | null;
  net_flow_cny: number | null;
  strength_score: number;
};

export type SectorRadarResponse = {
  trade_date: string | null;
  capital_flow_status: "direct" | "estimated" | "unavailable";
  flow_source: string;
  inflow: SectorRadarItem[];
  outflow: SectorRadarItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type RuntimeSettingsConfig = {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key_configured: boolean;
  tickflow_api_key_preview: string;
  tickflow_api_key_source: "runtime" | "env" | "none";
  tickflow_base_url: string;
  ifind_api_key_configured: boolean;
  ifind_api_key_preview: string;
  ifind_api_key_source: "runtime" | "env" | "none";
  ifind_base_url: string;
  ifind_service_id: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp";
  provider_timeout_seconds: number;
  runtime_config_path: string;
};

export type RuntimeSettingsResponse = {
  config: RuntimeSettingsConfig;
  saved: {
    candidate_provider?: "recent_limit_up" | "thsdk";
    kline_provider?: "tickflow";
    quote_provider?: "tickflow";
    tickflow_base_url?: string | null;
    ifind_base_url?: string | null;
    ifind_service_id?: "hexin-ifind-ds-stock-mcp" | "hexin-ifind-ds-news-mcp" | "hexin-ifind-ds-index-mcp" | null;
    provider_timeout_seconds?: number | null;
  };
};

export type RuntimeSettingsHealthProbe = {
  name: string;
  status: SourceStatusValue;
  latency_ms: number;
  detail: string;
};

export type RuntimeSettingsHealthResponse = {
  config: RuntimeSettingsConfig;
  probes: RuntimeSettingsHealthProbe[];
};

export type ScreenRunFilters = {
  min_market_cap_billion?: number | null;
  max_market_cap_billion?: number | null;
  kdj_j_max?: number | null;
  industries?: string[];
  market_types?: Array<"main" | "gem" | "star" | "bj">;
};

export type StrongStockScreeningItem = {
  symbol: string;
  name: string;
  industry: string | null;
  industry_strength: "strong" | "neutral" | "weak" | null;
  industry_score: number;
  industry_rank: number | null;
  industry_notes: string[];
  status: "focus" | "wait_pullback" | "reduce_risk" | "data_incomplete";
  score: number;
  rule_hits: string[];
  risk_flags: string[];
  severe_abnormal_warning: RiskCheckStatus;
  negative_news_status: RiskCheckStatus;
  negative_news_flags: string[];
  intraday_notes: string[];
  metrics: Record<string, unknown>;
  data_status: "complete" | "incomplete";
  source_trace: string[];
  gsgf: GsgfAnalysis | null;
};

export type KlineBar = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
};

export type StockKlineResponse = {
  symbol: string;
  source_status: StrongStockSourceStatus;
  bars: KlineBar[];
  gsgf_annotations: GsgfChartAnnotation[];
};

export type StockResearchResponse = {
  symbol: string;
  source_status: StrongStockSourceStatus[];
  profile: Record<string, unknown>;
  valuation: Record<string, unknown>;
  financials: Record<string, unknown>;
  events: Array<Record<string, unknown>>;
  news: Array<Record<string, unknown>>;
  notices: Array<Record<string, unknown>>;
  sector: Record<string, unknown>;
  generated_at: string;
};

export type WatchlistRiskItem = {
  symbol: string;
  name: string;
  industry: string | null;
  risk_action: "hold_watch" | "reduce" | "empty";
  risk_flags: string[];
  severe_abnormal_warning: RiskCheckStatus;
  negative_news_status: RiskCheckStatus;
  negative_news_flags: string[];
  intraday_notes: string[];
  metrics: Record<string, unknown>;
  source_trace: string[];
  gsgf: GsgfAnalysis | null;
};

export type StrongStockIntradayItem = {
  symbol: string;
  name: string;
  industry: string | null;
  action: "watch" | "low_buy_watch" | "reduce" | "avoid_chase" | "data_incomplete";
  group: string | null;
  tags: string[];
  last_price: number | null;
  pct_change: number | null;
  open_gap_pct: number | null;
  intraday_ma: number | null;
  latest_vs_intraday_ma_pct: number | null;
  volume: number | null;
  turnover_cny: number | null;
  gsgf_intraday_confirmation: GsgfIntradayConfirmation;
  signals: string[];
  source_trace: string[];
};

export type StrongStockScreeningResponse = {
  strategy: ScreenStrategy;
  strong_model_version: string;
  gsgf_model_version: string | null;
  sort_version: string;
  trade_date: string;
  source_status: StrongStockSourceStatus[];
  items: StrongStockScreeningItem[];
  watchlist_risk_items: WatchlistRiskItem[];
  generated_at: string;
};

export type StrongStockIntradaySnapshot = {
  source_status: StrongStockSourceStatus[];
  items: StrongStockIntradayItem[];
  generated_at: string;
};

export type WatchlistPoolResponse = {
  content: string;
  items: Array<{
    symbol: string;
    name: string | null;
    industry: string | null;
    group: string | null;
    tags: string[];
    note: string | null;
  }>;
};

export type WatchlistPoolItem = WatchlistPoolResponse["items"][number];

export type WatchlistPoolItemRequest = {
  symbol: string;
  name?: string | null;
  industry?: string | null;
  group?: string;
  tags?: string[];
  note?: string | null;
};

export type WatchlistGsgfStatusResponse = {
  items: Array<WatchlistPoolItem & { gsgf: GsgfAnalysis }>;
};

export type SourceStatusValue = "success" | "failed" | "disabled" | "missing_key";
export type RiskCheckStatus = "triggered" | "clear" | "unknown";

export type StrongStockSourceStatus = {
  source: string;
  status: SourceStatusValue;
  detail: string;
};

export type DataSourceStatusResponse = {
  items: StrongStockSourceStatus[];
};

export type RuntimeSettingsConfig = {
  candidate_provider: "recent_limit_up" | "thsdk";
  kline_provider: "tickflow";
  quote_provider: "tickflow";
  tickflow_api_key_configured: boolean;
  tickflow_api_key_preview: string;
  tickflow_api_key_source: "runtime" | "env" | "none";
  tickflow_base_url: string;
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
  signals: string[];
  source_trace: string[];
};

export type StrongStockScreeningResponse = {
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

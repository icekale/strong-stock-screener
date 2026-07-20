export type SourceStatusValue = "success" | "failed" | "disabled" | "missing_key" | "stale";
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
  evidence_refs: string[];
  diagnostics: Record<string, { score: number | null; flags: string[] }>;
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

export type HeatmapPeriodKey = "day" | "week" | "month" | "year";
export type HeatmapMarketKey = "all" | "sse" | "szse" | "hs300" | "zza500" | "cyb" | "kcb";
export type HeatmapSizeMode = "market_cap" | "turnover";
export type HeatmapTrendFilter = "all" | "rise" | "fall";

export type HeatmapStockNode = {
  symbol: string;
  code: string;
  name: string;
  industry: string;
  sub_industry: string | null;
  exchange: "SH" | "SZ" | "BJ";
  market: HeatmapMarketKey;
  price: number | null;
  change_pct: number;
  week_change_pct: number | null;
  month_change_pct: number | null;
  year_change_pct: number | null;
  turnover_cny: number | null;
  circulating_market_cap_cny: number | null;
  total_market_cap_cny: number | null;
  value: number;
  quote_time: string | null;
};

export type HeatmapBoardNode = {
  key: string;
  name: string;
  value: number;
  stock_count: number;
  advance_count: number;
  decline_count: number;
  unchanged_count: number;
  avg_change_pct: number | null;
  turnover_cny: number | null;
  children: HeatmapStockNode[];
};

export type HeatmapSummary = {
  trade_date: string | null;
  updated_at: string;
  stock_count: number;
  board_count: number;
  advance_count: number;
  decline_count: number;
  unchanged_count: number;
  turnover_cny: number | null;
  previous_turnover_cny: number | null;
  turnover_change_pct: number | null;
  index_change_pct: number | null;
};

export type HeatmapTreemapResponse = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  size_mode: HeatmapSizeMode;
  trend: HeatmapTrendFilter;
  board: string | null;
  summary: HeatmapSummary;
  nodes: HeatmapBoardNode[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type HeatmapQuoteItem = {
  symbol: string;
  price: number | null;
  change_pct: number;
  turnover_cny: number | null;
  quote_time: string | null;
};

export type HeatmapQuotesResponse = {
  market: HeatmapMarketKey;
  period: HeatmapPeriodKey;
  quotes: Record<string, HeatmapQuoteItem>;
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type HeatmapOverviewItem = {
  market: HeatmapMarketKey;
  name: string;
  change_pct: number | null;
  stock_count: number;
  updated_at: string;
};

export type HeatmapOverviewResponse = {
  period: HeatmapPeriodKey;
  markets: HeatmapOverviewItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type GsgfFunnelDiagnostics = {
  candidate_pool_count: number;
  after_static_filters_count: number;
  scan_limit_count: number;
  kline_success_count: number;
  kline_failure_count: number;
  data_incomplete_count: number;
  kdj_filtered_count: number;
  gsgf_structure_hit_count: number;
  confirmed_buy_count: number;
  low_buy_count: number;
  b_zone_a_point_count: number;
  volume_breakout_count: number;
  hard_risk_filtered_count: number;
  final_displayed_count: number;
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
  composite_score: number | null;
  calibration_rating: string;
  windows: GsgfCalibrationWindowStat[];
  examples: GsgfCalibrationExample[];
};

export type GsgfCalibrationDiagnosticGroup = {
  name: string;
  buckets: GsgfCalibrationBucket[];
};

export type GsgfRealCalibrationSummary = {
  trade_dates: string[];
  windows: number[];
  scanned_count: number;
  target_sample_count: number;
  skipped_count: number;
  buckets: GsgfCalibrationBucket[];
  unique_symbol_buckets: GsgfCalibrationBucket[];
  diagnostic_groups: GsgfCalibrationDiagnosticGroup[];
  samples: GsgfCalibrationSample[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type BackgroundJobStatus = "pending" | "running" | "success" | "failed" | "canceled";

export type BackgroundJobState = {
  job_id: string;
  type: string;
  status: BackgroundJobStatus;
  progress_current: number;
  progress_total: number;
  message: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result_path: string | null;
  result: unknown | null;
};

export type ScreenRunJobState = BackgroundJobState & {
  result: StrongStockScreeningResponse | null;
};

export type GsgfModelHealth = {
  best_signals: string[];
  weak_signals: string[];
  insufficient_sample_signals: string[];
  degraded_signals: string[];
  last_review_at: string | null;
  last_calibration_at: string | null;
  summary_text: string;
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

export type MarketIndexSnapshot = {
  symbol: string;
  name: string;
  last_price: number | null;
  change_pct: number | null;
  turnover_cny: number | null;
  source: string;
};

export type MarketOverviewResponse = {
  trade_date: string | null;
  turnover: MarketTurnoverSummary;
  advance_decline: MarketAdvanceDeclineSummary;
  indices: MarketIndexSnapshot[];
  sectors: MarketSectorStrengthItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type MarketRankingItem = {
  symbol: string;
  name: string | null;
  last_price: number | null;
  pct_change: number | null;
  turnover_rate: number | null;
  turnover_cny: number | null;
  volume: number | null;
  quote_time: string | null;
};

export type MarketRankingsResponse = {
  trade_date: string | null;
  pct_change_rank: MarketRankingItem[];
  turnover_rank: MarketRankingItem[];
  buckets: MarketEmotionBucket[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type AuctionSnapshotItem = {
  symbol: string;
  name: string | null;
  industry: string | null;
  themes: string[];
  hot_theme_rank: number | null;
  hot_theme_score: number | null;
  theme_auction_rank: number | null;
  theme_resonance: boolean;
  last_price: number | null;
  current_pct_change: number | null;
  open_gap_pct: number | null;
  turnover_rate: number | null;
  turnover_cny: number | null;
  volume: number | null;
  auction_score: number;
  tier: "strong_high_open" | "volume_leader" | "risk_overheat" | "weak_low_open" | "reversal_watch" | "neutral";
  action_note: string | null;
  signals: string[];
  risk_flags: string[];
  quote_time: string | null;
};

export type AuctionSnapshotResponse = {
  trade_date: string | null;
  session: "call_auction" | "pre_open" | "continuous" | "closed" | "unknown";
  snapshot_status: "fresh" | "cached" | "stale" | "missing";
  cache_age_seconds: number | null;
  metrics: {
    candidate_count: number;
    strong_high_open_count: number;
    high_risk_count: number;
    total_turnover_cny: number | null;
  };
  items: AuctionSnapshotItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type AuctionTimelinePoint = {
  label: string;
  target_time: string;
  snapshot_status: "captured" | "waiting";
  captured_at: string | null;
  metrics: AuctionSnapshotResponse["metrics"];
  items: AuctionSnapshotItem[];
};

export type AuctionTimelineResponse = {
  points: AuctionTimelinePoint[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type AuctionModelBucket = "selected" | "attack" | "watch" | "avoid";
export type AuctionModelCacheStatus = "generated" | "cached";
export type AuctionTop3LiveConfirmation = "buyable" | "watch" | "reject";

export type AuctionModelPredictionItem = {
  symbol: string;
  name: string;
  prob_3pct: number;
  bucket: AuctionModelBucket;
  rank: number | null;
  prev_close_price: number | null;
  market_cap_float: number | null;
  avg_amount_3d: number | null;
  feature_end_date: string | null;
  guard_rule: string | null;
  strategy_note: string | null;
  trend_reasons: string[];
  risk_flags: string[];
  data_quality: string[];
};

export type AuctionModelBacktestSummary = {
  period: string[];
  sample_count: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  payoff_ratio: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  average_return: number | null;
  breakeven_win_rate: number | null;
  capital_return_pct: number | null;
};

export type AuctionModelTop3Response = {
  run_id: string;
  trade_date: string;
  feature_end_date: string;
  model_version: string;
  feature_version: string;
  guard_rule: string;
  mode: string;
  cache_status: AuctionModelCacheStatus;
  backtest: AuctionModelBacktestSummary | null;
  items: AuctionModelPredictionItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type AuctionTop3RealtimeSnapshot = {
  last_price: number | null;
  current_pct_change: number | null;
  open_gap_pct: number | null;
  turnover_cny: number | null;
  turnover_rate: number | null;
  quote_time: string | null;
};

export type AuctionTop3LiveConfirmationItem = {
  symbol: string;
  name: string;
  model_rank: number | null;
  model_bucket: AuctionModelBucket;
  prob_3pct: number;
  confirmation: AuctionTop3LiveConfirmation;
  realtime: AuctionTop3RealtimeSnapshot | null;
  reasons: string[];
  risk_flags: string[];
  data_quality: string[];
};

export type AuctionTop3LiveConfirmationResponse = {
  trade_date: string;
  model_run_id: string | null;
  cache_status: AuctionModelCacheStatus;
  items: AuctionTop3LiveConfirmationItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type AuctionTop3EntryPolicy = "open_0930" | "after_0935_confirm" | "before_1000_strength" | "close_follow";
export type AuctionTop3ExitPolicy =
  | "intraday_stop"
  | "intraday_take_profit"
  | "close_exit"
  | "next_open_exit"
  | "next_close_exit";
export type AuctionTop3TradeLabel = "win" | "loss" | "neutral" | "data_incomplete";

export type AuctionTop3TrainingSettings = {
  record_signal_samples: boolean;
  generate_simulated_trade_samples: boolean;
  include_manual_trade_samples_in_training: boolean;
  training_window_days: number;
  simulated_initial_capital: number;
  simulated_position_pct: number;
};

export type AuctionTop3TrainingSummary = {
  enabled: boolean;
  signal_sample_count: number;
  simulated_trade_sample_count: number;
  manual_trade_sample_count: number;
  date_range: string[];
  training_window_days: number;
  latest_generated_at: string | null;
  simulated_profit_summary: Record<string, unknown>;
  quality_notes: string[];
};

export type AuctionTop3SimulatedTradeSample = {
  sample_id: string;
  signal_sample_id: string;
  portfolio_id: string;
  trade_date: string;
  symbol: string;
  entry_policy: AuctionTop3EntryPolicy;
  entry_price: number | null;
  entry_time: string | null;
  exit_policy: AuctionTop3ExitPolicy;
  exit_price: number | null;
  exit_time: string | null;
  position_pct: number;
  return_pct: number | null;
  profit_amount: number | null;
  max_drawdown_pct: number | null;
  max_favorable_pct: number | null;
  label: AuctionTop3TradeLabel;
};

export type AuctionTop3SimulatedPerformancePoint = {
  portfolio_id: string;
  trade_date: string;
  entry_policy: AuctionTop3EntryPolicy;
  exit_policy: AuctionTop3ExitPolicy;
  trade_count: number;
  win_count: number;
  loss_count: number;
  daily_return_pct: number | null;
  cumulative_return_pct: number | null;
  equity: number | null;
  max_drawdown_pct: number | null;
  created_at: string;
};

export type AuctionTop3PerformanceResponse = {
  summary: Record<string, unknown>;
  points: AuctionTop3SimulatedPerformancePoint[];
  trades: AuctionTop3SimulatedTradeSample[];
  generated_at: string;
};

export type AuctionTop3TrainingGenerateResponse = {
  saved_count: number;
  performance: AuctionTop3PerformanceResponse;
};

export type AuctionReviewSnapshot = {
  open_gap_pct: number | null;
  current_pct_change: number | null;
  turnover_rate: number | null;
  turnover_cny: number | null;
  volume: number | null;
  auction_score: number;
  rank: number | null;
  tier: string;
  signals: string[];
  risk_flags: string[];
  quote_time: string | null;
};

export type AuctionReviewOutcome = {
  peak_pct: number | null;
  close_pct: number | null;
  drawdown_pct: number | null;
  limit_up: boolean | null;
  open_pct: number | null;
  strong_follow: boolean | null;
  status: string;
};

export type AuctionReviewScore = {
  intraday_score: number | null;
  day_score: number | null;
  next_day_score: number | null;
  total_score: number | null;
};

export type AuctionReviewRecord = {
  trade_date: string;
  symbol: string;
  name: string | null;
  industry: string | null;
  selected_at_label: string;
  selected_at: string | null;
  auction_snapshot: AuctionReviewSnapshot;
  rule_tags: string[];
  source_status: StrongStockSourceStatus[];
  intraday_result: AuctionReviewOutcome;
  day_result: AuctionReviewOutcome;
  next_day_result: AuctionReviewOutcome;
  score: AuctionReviewScore;
  review_status: "pending" | "intraday_done" | "day_done" | "next_day_done" | "data_incomplete";
};

export type AuctionRuleBucket = {
  rule_tag: string;
  sample_count: number;
  win_rate: number | null;
  avg_score: number | null;
  avg_intraday_peak_pct: number | null;
  avg_close_pct: number | null;
  avg_next_open_pct: number | null;
  avg_drawdown_pct: number | null;
  failure_count: number;
  suggestion: string;
};

export type AuctionReviewSummary = {
  trade_date: string | null;
  record_count: number;
  pending_count: number;
  completed_count: number;
  data_incomplete_count: number;
  records: AuctionReviewRecord[];
  buckets: AuctionRuleBucket[];
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

export type SectorWorkbenchMode = "strength" | "main_flow";
export type SectorWorkbenchScope = "theme" | "industry";
export type SectorWorkbenchScopeRequest = SectorWorkbenchScope | "auto";
export type SectorFlowStatus = "direct" | "estimated" | "unavailable";

export type SectorWorkbenchTheme = {
  name: string;
  scope: SectorWorkbenchScope;
  limit_up_count: number;
  strength_score: number;
  main_flow_cny: number | null;
  turnover_cny: number | null;
  change_pct: number | null;
  leader: string | null;
  member_count: number;
  source: string;
  flow_status: SectorFlowStatus;
};

export type SectorWorkbenchPoint = {
  time: string;
  value: number;
  sampled_at: string;
};

export type SectorWorkbenchSeries = {
  name: string;
  scope: SectorWorkbenchScope;
  metric: SectorWorkbenchMode;
  points: SectorWorkbenchPoint[];
};

export type SectorWorkbenchStock = {
  symbol: string;
  name: string | null;
  industry: string | null;
  themes: string[];
  pct_change: number | null;
  turnover_cny: number | null;
  turnover_rate: number | null;
  limit_up: boolean;
  board_count: number;
  auction_pct_change: number | null;
  auction_turnover_cny: number | null;
  seal_amount_cny: number | null;
  risk_flags: string[];
};

export type SectorWorkbenchResponse = {
  scope: SectorWorkbenchScope;
  mode: SectorWorkbenchMode;
  trade_date: string | null;
  themes: SectorWorkbenchTheme[];
  selected_themes: string[];
  series: SectorWorkbenchSeries[];
  related_tags: string[];
  stocks: SectorWorkbenchStock[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type SectorWorkbenchCacheSummary = {
  trade_date: string | null;
  sample_count: number;
  latest_sampled_at: string | null;
  modes: SectorWorkbenchMode[];
  scopes: SectorWorkbenchScope[];
  metrics: SectorWorkbenchMode[];
  sample_sources: string[];
  names: string[];
};

export type SectorWorkbenchStatusResponse = {
  trade_date: string;
  sample_window_open: boolean;
  sampler_enabled: boolean;
  sampler_running: boolean;
  interval_seconds: number | null;
  idle_seconds: number | null;
  cache: SectorWorkbenchCacheSummary;
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type SectorReplicaMode = "strength" | "main_flow";

export type SectorReplicaPlate = {
  code: string;
  name: string;
  val: number;
  ztcount: number;
  display_value: string | null;
};

export type SectorReplicaChartSeries = {
  name: string;
  type: "line";
  data: Array<number | null>;
  smooth: boolean;
  showSymbol: boolean;
};

export type SectorReplicaQxLive = {
  Aaxis: string[];
  zflist: number[];
  series: Record<string, Array<number | null>>;
};

export type SectorReplicaStockRow = {
  symbol: string;
  code: string;
  name: string | null;
  pct_change: number | null;
  turnover_cny: number | null;
  circulating_value_cny: number | null;
  board_label: string;
  auction_pct_change: number | null;
  auction_amount_cny: number | null;
  auction_volume_ratio: number | null;
  buy_ratio_pct: number | null;
  seal_amount_cny: number | null;
  leader_tag: string | null;
  themes: string[];
  industry: string | null;
  compat_row: unknown[];
};

export type SectorReplicaStocksResponse = {
  board_code: string | null;
  sub_theme: string | null;
  rows: SectorReplicaStockRow[];
  related_tags: string[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type SectorReplicaRadarResponse = {
  result: "success";
  mode: SectorReplicaMode;
  trade_date: string | null;
  axis: string[];
  qxlive: SectorReplicaQxLive;
  plates: SectorReplicaPlate[];
  checkplate: string[];
  legend: string[];
  series: SectorReplicaChartSeries[];
  stocks: SectorReplicaStockRow[];
  related_tags: string[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type PlateRotationSource = "kaipan" | "ths";

export type PlateRotationThemeItem = {
  rank: number;
  code: string;
  name: string;
  score: number;
  value_type: "score" | "pct" | string;
  color: "red" | "green" | string;
};

export type PlateRotationReferenceResponse = {
  source: PlateRotationSource | string;
  themes: PlateRotationThemeItem[];
  source_status: StrongStockSourceStatus[];
};

export type ShortTermSentimentStockItem = {
  symbol: string;
  name: string;
  industry: string | null;
  board_count: number;
  limit_up_hits_20d: number;
  break_board_count: number;
  last_limit_up_date: string | null;
  first_seal_time: string | null;
  last_seal_time: string | null;
  board_note: string | null;
  limit_up_evidence: string[];
};

export type ShortTermSentimentLadderGroup = {
  board_count: number;
  label: string;
  items: ShortTermSentimentStockItem[];
};

export type ShortTermSentimentIndustryItem = {
  name: string;
  limit_up_count: number;
  break_board_count: number;
  max_consecutive_boards: number;
  leader: string | null;
  symbols: string[];
  strength_score: number;
};

export type ShortTermSentimentResponse = {
  trade_date: string;
  metrics: {
    limit_up_count: number;
    break_board_count: number;
    max_consecutive_boards: number;
    hot_industry_count: number;
  };
  limit_up_pool: ShortTermSentimentStockItem[];
  break_board_pool: ShortTermSentimentStockItem[];
  ladder: ShortTermSentimentLadderGroup[];
  hot_industries: ShortTermSentimentIndustryItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type MarketEmotionLevel = "冰点" | "一般" | "良好" | "火爆";

export type MarketEmotionBucket = {
  label: string;
  min_pct: number | null;
  max_pct: number | null;
  count: number | null;
  source: string;
};

export type MarketEmotionMetrics = {
  emotion_score: number;
  emotion_level: MarketEmotionLevel;
  limit_up_count: number;
  break_board_count: number;
  limit_down_count: number | null;
  losing_effect_score: number | null;
  max_consecutive_boards: number;
  advance_count: number | null;
  decline_count: number | null;
  seal_rate_pct: number | null;
  turnover_cny: number | null;
  turnover_change_cny: number | null;
  turnover_change_pct: number | null;
  main_flow_cny: number | null;
  yesterday_limit_up_performance_pct: number | null;
  yesterday_ladder_performance_pct: number | null;
};

export type MarketEmotionSample = {
  trade_date: string;
  sampled_at: string;
  emotion_score: number;
  emotion_level: MarketEmotionLevel;
  limit_up_count: number;
  break_board_count: number;
  limit_down_count: number | null;
  losing_effect_score: number | null;
  max_consecutive_boards: number;
  advance_count: number | null;
  decline_count: number | null;
  seal_rate_pct: number | null;
  turnover_cny: number | null;
  turnover_change_pct: number | null;
};

export type MarketEmotionSnapshotResponse = {
  trade_date: string;
  metrics: MarketEmotionMetrics;
  buckets: MarketEmotionBucket[];
  samples: MarketEmotionSample[];
  source_status: StrongStockSourceStatus[];
  notes: string[];
  generated_at: string;
};

export type SentimentSnapshotStatus = "fresh" | "cached" | "missing";

export type SentimentSummaryMetrics = {
  emotion_score: number;
  emotion_level: MarketEmotionLevel;
  limit_up_count: number;
  break_board_count: number;
  limit_down_count: number | null;
  losing_effect_score: number | null;
  max_consecutive_boards: number;
  advance_count: number | null;
  decline_count: number | null;
  seal_rate_pct: number | null;
  turnover_cny: number | null;
  turnover_change_cny: number | null;
  turnover_change_pct: number | null;
};

export type SentimentSummaryResponse = {
  trade_date: string;
  snapshot_status: SentimentSnapshotStatus;
  cached_at: string | null;
  metrics: SentimentSummaryMetrics;
  hot_industries: ShortTermSentimentIndustryItem[];
  source_status: StrongStockSourceStatus[];
  notes: string[];
  generated_at: string;
};

export type SentimentDetailResponse = {
  trade_date: string;
  snapshot_status: SentimentSnapshotStatus;
  cached_at: string | null;
  sentiment: ShortTermSentimentResponse;
  market_emotion: MarketEmotionSnapshotResponse;
};

export type SentimentMarketState = "冰点" | "修复" | "主升" | "高潮" | "分歧" | "退潮";
export type SentimentTradePermission = "空仓等待" | "轻仓试错" | "强势进攻" | "只低吸" | "只卖不追";
export type SentimentRiskLevel = "低" | "中" | "高";

export type SentimentMainSectorSignal = {
  name: string;
  strength_score: number;
  limit_up_count: number;
  break_board_count: number;
  max_consecutive_boards: number;
  leader: string | null;
  symbols: string[];
};

export type SentimentDecisionResponse = {
  trade_date: string;
  market_state: SentimentMarketState;
  trade_permission: SentimentTradePermission;
  risk_level: SentimentRiskLevel;
  confidence: number;
  score_change: number | null;
  main_sectors: SentimentMainSectorSignal[];
  reasons: string[];
  risks: string[];
  generated_at: string;
};

export type SentimentDecisionOutcome = {
  trade_date: string;
  next_day_index_pct: number | null;
  next_day_limit_up_count: number | null;
  next_day_limit_down_count: number | null;
  hit: boolean;
  score: number;
  reason: string;
};

export type SentimentReviewSummary = {
  trade_date: string;
  sample_count: number;
  hit_count: number;
  hit_rate_pct: number;
  avg_score: number;
  outcomes: SentimentDecisionOutcome[];
};

export type SentimentWatchlistAlert = {
  symbol: string;
  name: string;
  group: string | null;
  tags: string[];
  action: "重点盯" | "等确认" | "风险回避";
  matched_sector: string | null;
  reasons: string[];
};

export type SentimentWatchlistAlertsResponse = {
  trade_date: string;
  items: SentimentWatchlistAlert[];
};

export type ShortTermIntradaySentimentItem = {
  symbol: string;
  name: string;
  industry: string | null;
  pool_tags: string[];
  action: "watch" | "low_buy_watch" | "reduce" | "avoid_chase" | "data_incomplete";
  last_price: number | null;
  pct_change: number | null;
  open_gap_pct: number | null;
  intraday_ma: number | null;
  latest_vs_intraday_ma_pct: number | null;
  turnover_cny: number | null;
  signals: string[];
};

export type ShortTermIntradaySentimentResponse = {
  trade_date: string;
  metrics: {
    watched_count: number;
    alert_count: number;
    reduce_count: number;
    low_buy_watch_count: number;
    avoid_chase_count: number;
  };
  items: ShortTermIntradaySentimentItem[];
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type ShortTermIntradaySignalAlert = {
  symbol: string;
  name: string;
  industry: string | null;
  action: "watch" | "low_buy_watch" | "reduce" | "avoid_chase" | "data_incomplete";
  severity: "high" | "medium" | "low";
  pool_tags: string[];
  pct_change: number | null;
  turnover_cny: number | null;
  reasons: string[];
};

export type ShortTermIntradaySignalDigest = {
  title: string;
  trade_date: string;
  alert_count: number;
  alerts: ShortTermIntradaySignalAlert[];
  message_text: string;
  source_status: StrongStockSourceStatus[];
  generated_at: string;
};

export type SentimentMonitorConfig = {
  enabled: boolean;
  interval_minutes: 1 | 2 | 3;
  cooldown_minutes: number;
  limit: number;
  emotion_score_change_threshold: number;
  emotion_score_15m_threshold: number;
  break_board_jump_threshold: number;
  limit_down_jump_threshold: number;
  seal_rate_drop_threshold: number;
  limit_up_jump_threshold: number;
  losing_effect_jump_threshold: number;
};

export type SentimentMutationAlert = {
  type: string;
  severity: "high" | "medium" | "low";
  title: string;
  message: string;
  previous_value: number | null;
  current_value: number | null;
  threshold: number;
  generated_at: string;
};

export type SentimentMonitorStatus = {
  enabled: boolean;
  running: boolean;
  in_trading_session: boolean;
  config: SentimentMonitorConfig;
  last_sampled_at: string | null;
  last_trade_date: string | null;
  last_emotion_score: number | null;
  last_notification_at: string | null;
  last_error: string | null;
  last_alerts: SentimentMutationAlert[];
};

export type ModelMaintenanceProvider = "openai" | "deepseek" | "openai_compatible";
export type ModelMaintenanceHealthStatus =
  | "normal"
  | "watch"
  | "degraded"
  | "insufficient_sample"
  | "data_unreliable";
export type ModelMaintenanceRuleStatus =
  | "effective"
  | "neutral"
  | "over_strict"
  | "under_strict"
  | "degraded"
  | "insufficient_sample";
export type ModelMaintenanceSuggestionType =
  | "observe"
  | "adjust_weight"
  | "loosen_filter"
  | "tighten_filter"
  | "disable_rule_temporarily"
  | "data_check";
export type ModelMaintenanceSuggestionStatus = "pending" | "accepted" | "ignored" | "snoozed";

export type ModelMaintenanceSuggestion = {
  suggestion_id: string;
  type: ModelMaintenanceSuggestionType;
  title: string;
  reason: string;
  evidence_refs: string[];
  risk: string;
  confidence: number;
  suggested_action: string;
  status: ModelMaintenanceSuggestionStatus;
};

export type ModelMaintenanceRuleDiagnostic = {
  rule_name: string;
  status: ModelMaintenanceRuleStatus;
  evidence: string[];
  confidence: number;
};

export type ModelMaintenancePacket = {
  packet_id: string;
  generated_at: string;
  trade_date: string | null;
  model_name: string;
  model_version: string | null;
  screen_strategy: string | null;
  screen_params: Record<string, unknown>;
  source_status: StrongStockSourceStatus[];
  latest_screen_run: Record<string, unknown>;
  review_summary: Record<string, unknown>;
  calibration_summary: Record<string, unknown>;
  false_negative_cases: Array<Record<string, unknown>>;
  false_positive_cases: Array<Record<string, unknown>>;
  data_quality_notes: string[];
  model_sections: Record<string, unknown>;
  packet_url: string | null;
};

export type ModelMaintenanceReport = {
  report_id: string;
  packet_id: string;
  provider: ModelMaintenanceProvider;
  model: string;
  generated_at: string;
  health_status: ModelMaintenanceHealthStatus;
  summary: string;
  key_findings: string[];
  rule_diagnostics: ModelMaintenanceRuleDiagnostic[];
  suggestions: ModelMaintenanceSuggestion[];
  disclaimer: string;
};

export type AiAnalysisPublicConfig = {
  enabled: boolean;
  provider: ModelMaintenanceProvider;
  base_url: string;
  model: string;
  api_key_configured: boolean;
  api_key_preview: string;
  api_key_source: "runtime" | "env" | "none";
  run_after_daily_review: boolean;
  run_after_weekly_calibration: boolean;
};

export type AiAnalysisSettingsUpdate = {
  enabled: boolean;
  provider: ModelMaintenanceProvider;
  base_url: string;
  model: string;
  api_key?: string | null;
  run_after_daily_review: boolean;
  run_after_weekly_calibration: boolean;
};

export type GsgfAutoReviewConfig = {
  auto_snapshot_enabled: boolean;
  daily_review_enabled: boolean;
  daily_review_time: string;
  weekly_calibration_enabled: boolean;
  weekly_calibration_weekday: number;
  weekly_calibration_time: string;
  weekly_calibration_trade_days: number;
  weekly_calibration_scan_limit: number;
  windows: number[];
  kline_count: number;
  notify_on_success: boolean;
  notify_on_degradation: boolean;
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
  tdx_api_key_configured: boolean;
  tdx_api_key_preview: string;
  tdx_api_key_source: "runtime" | "env" | "none";
  tdx_base_url: string;
  provider_timeout_seconds: number;
  runtime_config_path: string;
  notifications: NotificationSettingsPublic;
  sentiment_monitor: SentimentMonitorConfig;
  gsgf_auto_review: GsgfAutoReviewConfig;
  ai_analysis: AiAnalysisPublicConfig;
  auction_top3_training: AuctionTop3TrainingSettings;
};

export type NotificationChannelType = "wechat_work" | "feishu" | "telegram" | "email";

export type NotificationChannelConfig = {
  id: string;
  type: NotificationChannelType;
  name: string;
  enabled: boolean;
  webhook_url?: string | null;
  bot_token?: string | null;
  chat_id?: string | null;
  smtp_host?: string | null;
  smtp_port?: number;
  smtp_username?: string | null;
  smtp_password?: string | null;
  smtp_sender?: string | null;
  smtp_recipients?: string[];
  smtp_use_tls?: boolean;
};

export type NotificationChannelPublic = {
  id: string;
  type: NotificationChannelType;
  name: string;
  enabled: boolean;
  webhook_configured: boolean;
  bot_token_configured: boolean;
  chat_id_configured: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_sender: string;
  smtp_recipients: string[];
  smtp_use_tls: boolean;
};

export type NotificationSettingsPublic = {
  channels: NotificationChannelPublic[];
};

export type NotificationSendResult = {
  results: Array<{
    channel_id: string;
    channel_name: string;
    type: NotificationChannelType | null;
    status: "success" | "failed" | "disabled" | "not_found";
    detail: string;
  }>;
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
    tdx_base_url?: string | null;
    provider_timeout_seconds?: number | null;
    notification_channels?: NotificationChannelConfig[];
    sentiment_monitor?: SentimentMonitorConfig;
    gsgf_auto_review?: GsgfAutoReviewConfig;
    ai_analysis?: AiAnalysisSettingsUpdate;
    auction_top3_training?: AuctionTop3TrainingSettings;
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
  chanlun_min_confluence_score?: number | null;
  chanlun_require_confirmed_buy?: boolean;
};

export type ChanlunScreeningPeriodSummary = {
  period: ChanlunPeriod;
  availability: ChanlunAvailability;
  direction: ChanlunDirection;
  latest_signal_type: ChanlunSignalType | null;
  latest_signal_at: string | null;
  latest_divergence_type: ChanlunDivergenceType | null;
  latest_divergence_at: string | null;
  signal_age_seconds: number | null;
  last_closed_bar_at: string | null;
};

export type ChanlunScreeningSummary = {
  availability: "ready" | "partial" | "unavailable";
  freshness: "fresh" | "stale" | "insufficient";
  periods: ChanlunScreeningPeriodSummary[];
  confluence_score: number;
  bullish_periods: number;
  bearish_periods: number;
  has_confirmed_buy: boolean;
  has_confirmed_sell: boolean;
  latest_confirmed_at: string | null;
  rule_version: string;
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
  chanlun_summary?: ChanlunScreeningSummary | null;
  czsc_score_v2?: number | null;
  czsc_v2_eligible?: boolean | null;
  czsc_v2_shadow_rank?: number | null;
  czsc_v2_evidence?: CzscSignalEvidenceSummary[] | null;
  czsc_v2_status?: CzscResearchStatus | null;
  czsc_v2_rule_version?: string | null;
};

export type KlineBar = {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount?: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
};

export type StockKlinePeriod = "1d" | "60m" | "30m" | "5m";
export type ChanlunPeriod = StockKlinePeriod;
export type ChanlunStatus = "observing" | "provisional" | "confirmed" | "final";
export type ChanlunDirection = "up" | "down" | "unknown";
export type ChanlunAvailability = "ready" | "backfilling" | "insufficient_bars" | "stale" | "unavailable";
export type ChanlunDivergenceType = "top" | "bottom" | "consolidation";
export type ChanlunSignalType = "one_buy" | "one_sell" | "two_buy" | "two_sell" | "three_buy" | "three_sell";
export type ChanlunConfluenceType =
  | "class_two_buy"
  | "class_two_sell"
  | "class_three_buy"
  | "class_three_sell"
  | "sub_two_buy"
  | "sub_two_sell"
  | "sub_three_buy"
  | "sub_three_sell";
export type ChanlunLayerKey = "fractals" | "strokes" | "segments" | "zones" | "divergences" | "signals";
export type CzscResearchStatus = "ready" | "pending" | "stale" | "unavailable" | "insufficient_bars" | "adjustment_mismatch";
export type CzscEvidenceFamily = "trend_context" | "second_buy" | "third_buy" | "zone_confluence" | "divergence" | "sell_risk";
export type CzscEvidenceRole = "primary" | "confirmation" | "risk" | "observation";
export type CzscEvidenceDirection = "bullish" | "bearish" | "neutral";

export type CzscSignalEvidence = {
  id: string;
  catalog_id: string;
  family: CzscEvidenceFamily;
  role: CzscEvidenceRole;
  direction: CzscEvidenceDirection;
  period: ChanlunPeriod | null;
  higher_period: ChanlunPeriod | null;
  lower_period: ChanlunPeriod | null;
  occurred_at: string;
  last_closed_bar_at: string;
  signal_name: string;
  params: Record<string, unknown>;
  engine_version: string;
  catalog_version: string;
  rule_version: string;
};

export type CzscSignalEvidenceSummary = Pick<
  CzscSignalEvidence,
  "id" | "catalog_id" | "family" | "role" | "direction" | "period" | "higher_period" | "lower_period" | "occurred_at"
> & {
  reason: string;
};

export type CzscResearchSnapshot = {
  status: CzscResearchStatus;
  symbol: string;
  current_states: CzscSignalEvidence[];
  events: CzscSignalEvidence[];
  last_closed_by_period: Partial<Record<ChanlunPeriod, string>>;
  input_snapshot_id: string;
  score: number | null;
  eligible: boolean;
  engine_version: string;
  catalog_version: string;
  rule_version: string;
  source_status: StrongStockSourceStatus[];
  adjustment_mode: string;
  calculated_at: string;
};

export type CzscV2CandidateScore = {
  symbol: string;
  status: CzscResearchStatus;
  score: number | null;
  shadow_rank: number | null;
  eligible: boolean;
  baseline_rank: number;
  evidence: CzscSignalEvidenceSummary[];
  input_snapshot_id: string;
  rule_version: string;
};

export type CzscV2BatchStatus = "pending" | "ready" | "partial" | "unavailable";

export type CzscV2BatchResult = {
  batch_id: string;
  job_id: string;
  status: CzscV2BatchStatus;
  trade_date: string;
  pool_size: number;
  completed_count: number;
  items: CzscV2CandidateScore[];
};

export type CzscShadowScreeningJobResponse = {
  job: BackgroundJobState;
  batch: CzscV2BatchResult | null;
};

export type ChanlunFractal = {
  id: string;
  occurred_at: string;
  price: number;
  mark: "top" | "bottom";
  status: ChanlunStatus;
};

export type ChanlunStroke = {
  id: string;
  start_at: string;
  start_price: number;
  end_at: string;
  end_price: number;
  direction: ChanlunDirection;
  status: ChanlunStatus;
};

export type ChanlunZone = {
  id: string;
  start_at: string;
  end_at: string;
  high: number;
  low: number;
  virtual: boolean;
  status: ChanlunStatus;
};

export type ChanlunDivergence = {
  id: string;
  type: ChanlunDivergenceType;
  occurred_at: string;
  reference_occurred_at: string;
  direction: ChanlunDirection;
  reference_stroke_id: string;
  current_stroke_id: string;
  reference_price: number;
  current_price: number;
  reference_macd_strength: number;
  current_macd_strength: number;
  coefficient: number;
  zone_count: number;
  status: ChanlunStatus;
  rule_version: string;
};

export type ChanlunSignal = {
  id: string;
  type: ChanlunSignalType;
  occurred_at: string;
  price: number;
  divergence_id: string | null;
  stroke_id: string;
  status: ChanlunStatus;
  rule_version: string;
};

export type ChanlunConfluenceSignal = {
  id: string;
  type: ChanlunConfluenceType;
  higher_period: ChanlunPeriod;
  lower_period: ChanlunPeriod;
  occurred_at: string;
  price: number;
  source_signal_id: string | null;
  higher_zone_id: string | null;
  status: ChanlunStatus;
  reason: string;
  rule_version: string;
};

export type ChanlunAnalysisResponse = {
  symbol: string;
  period: ChanlunPeriod;
  availability: ChanlunAvailability;
  bars: KlineBar[];
  fractals: ChanlunFractal[];
  strokes: ChanlunStroke[];
  segments: ChanlunStroke[];
  zones: ChanlunZone[];
  divergences: ChanlunDivergence[];
  signals: ChanlunSignal[];
  source_status: StrongStockSourceStatus[];
  calculated_at: string;
  last_closed_bar_at: string | null;
  adjustment_mode: string;
  rule_version: string;
};

export type ChanlunPeriodSummary = {
  period: ChanlunPeriod;
  availability: ChanlunAvailability;
  direction: ChanlunDirection;
  latest_zone: ChanlunZone | null;
  latest_divergence: ChanlunDivergence | null;
  latest_signal: ChanlunSignal | null;
  last_closed_bar_at: string | null;
};

export type ChanlunWorkspaceResponse = {
  symbol: string;
  periods: ChanlunPeriodSummary[];
  analysis: ChanlunAnalysisResponse;
  confluence_signals: ChanlunConfluenceSignal[];
};

export type ChanlunReplayFrame = {
  closed_at: string;
  direction: ChanlunDirection;
  latest_zone: ChanlunZone | null;
  new_divergences: ChanlunDivergence[];
  new_signals: ChanlunSignal[];
};

export type ChanlunReplayResponse = {
  symbol: string;
  period: ChanlunPeriod;
  availability: ChanlunAvailability;
  frames: ChanlunReplayFrame[];
  source_status: StrongStockSourceStatus[];
  adjustment_mode: string;
  rule_version: string;
};

export type ChanlunBacktestWindowStat = {
  horizon_bars: number;
  sample_count: number;
  win_rate_pct: number | null;
  avg_return_pct: number | null;
  median_return_pct: number | null;
  avg_max_drawdown_pct: number | null;
  profit_loss_ratio: number | null;
};

export type ChanlunBacktestBucket = {
  signal_type: ChanlunSignalType;
  sample_count: number;
  windows: ChanlunBacktestWindowStat[];
};

export type ChanlunBacktestResponse = {
  symbol: string;
  period: ChanlunPeriod;
  availability: ChanlunAvailability;
  horizons: number[];
  entry_rule: "next_bar_open";
  sample_count: number;
  buckets: ChanlunBacktestBucket[];
  source_status: StrongStockSourceStatus[];
  adjustment_mode: string;
  rule_version: string;
};

export type ChanlunAlertItem = {
  key: string;
  symbol: string;
  period: ChanlunPeriod;
  signal_type: ChanlunSignalType;
  occurred_at: string;
  price: number;
  rule_version: string;
  first_seen_at: string;
};

export type ChanlunAlertListResponse = {
  items: ChanlunAlertItem[];
};

export type ChanlunAlertRefreshResponse = {
  symbol: string;
  period: ChanlunPeriod;
  baselined: boolean;
  created: ChanlunAlertItem[];
  source_status: StrongStockSourceStatus[];
};

export type ChanlunPaperOrderStatus =
  | "draft"
  | "awaiting_confirmation"
  | "simulated_open"
  | "filled"
  | "rejected"
  | "expired"
  | "cancelled";

export type ChanlunPaperOrder = {
  id: string;
  symbol: string;
  side: "buy";
  quantity: number;
  reference_price: number;
  notional: number;
  status: ChanlunPaperOrderStatus;
  reasons: string[];
  signal_snapshot: Record<string, unknown>;
  rule_version: string;
  created_at: string;
  approved_at: string | null;
  fill_price: number | null;
  fill_notional: number | null;
  slippage_bps: number | null;
  quote_time: string | null;
  filled_at: string | null;
  cancelled_at: string | null;
  rejection_reason: string | null;
};

export type ChanlunPaperPosition = {
  symbol: string;
  quantity: number;
  average_price: number;
  latest_price: number | null;
  quote_time: string | null;
  valuation_status: "live" | "unavailable";
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
};

export type ChanlunPaperAuditRecord = {
  id: number;
  order_id: string;
  event: "created" | "approved" | "rejected" | "cancelled" | "filled";
  occurred_at: string;
  details: Record<string, unknown>;
};

export type ChanlunPaperAccount = {
  initial_cash: number;
  reserved_cash: number;
  available_cash: number;
  total_equity: number;
  unrealized_pnl: number | null;
  realized_pnl: number;
  valuation_complete: boolean;
  valuation_time: string | null;
  positions: ChanlunPaperPosition[];
  orders: ChanlunPaperOrder[];
  audit_records: ChanlunPaperAuditRecord[];
};

export type ChanlunBackfillRequest = {
  history_days?: number;
};

export type ChanlunSymbolMatch = {
  symbol: string;
  name: string;
};

export type ChanlunSymbolSearchResponse = {
  items: ChanlunSymbolMatch[];
  source_status: StrongStockSourceStatus[];
};

export type StockKlineResponse = {
  symbol: string;
  period: StockKlinePeriod;
  source_status: StrongStockSourceStatus;
  bars: KlineBar[];
  gsgf_annotations: GsgfChartAnnotation[];
};

export type StockQuoteResponse = {
  symbol: string;
  name: string | null;
  industry: string | null;
  last_price: number | null;
  prev_close: number | null;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  pct_change: number | null;
  turnover_rate: number | null;
  turnover_cny: number | null;
  volume: number | null;
  quote_time: string | null;
  total_market_cap_cny: number | null;
  circulating_market_cap_cny: number | null;
  pe_ttm: number | null;
  pe_static: number | null;
  pb: number | null;
  valuation_source_status: StrongStockSourceStatus | null;
  source_status: StrongStockSourceStatus;
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
  gsgf_funnel: GsgfFunnelDiagnostics;
  gsgf_observation_items: StrongStockScreeningItem[];
  watchlist_risk_items: WatchlistRiskItem[];
  czsc_v2_job_id?: string | null;
  czsc_v2_status?: CzscV2BatchStatus | null;
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

export type SystemConfidence = "fresh" | "stale" | "partial" | "degraded" | "unavailable";

export type SystemCacheItem = {
  name: string;
  group: string;
  ttl_seconds: number;
  size: number;
  fresh_count: number;
  refreshing_count: number;
  hits: number;
  misses: number;
  stale_hits: number;
  refresh_count: number;
  refresh_error_count: number;
  last_refresh_started_at: number | null;
  last_refresh_finished_at: number | null;
  last_error: string | null;
  oldest_expires_in_seconds: number | null;
};

export type SystemCacheSummary = {
  total: number;
  items: SystemCacheItem[];
};

export type SystemJobStatus = {
  name: string;
  running: boolean;
  enabled: boolean;
  detail: string;
};

export type SystemStatusResponse = {
  status: "ok" | "degraded";
  generated_at: string;
  cache: SystemCacheSummary;
  jobs: SystemJobStatus[];
  confidence: SystemConfidence;
};

export type SystemCacheClearResponse = {
  cleared: string[];
};

export type CapitalSignalStage = "intraday" | "post_close" | "disclosure";
export type CapitalEvidenceLevel = "常规" | "观察" | "疑似" | "较强";
export type HuijinEtfRole = "core" | "validator";
export type EtfActivityDirection = "increase" | "decrease" | "flat" | "unknown";
export type EtfValidationState = "confirmed_increase" | "confirmed_decrease" | "divergent" | "incomplete";
export type HuijinBaselineSourceKind = "reported" | "derived";

export type CapitalSignalMetadata = {
  generated_at: string;
  trade_date: string;
  as_of: string;
  signal_stage: CapitalSignalStage;
  model_version: string;
  source_status: StrongStockSourceStatus[];
};

export type MarginSummary = {
  balance_cny: number | null;
  financing_balance_cny: number | null;
  securities_lending_balance_cny: number | null;
  financing_buy_cny: number | null;
  change_cny: number | null;
  change_pct: number | null;
  available_markets: number;
  expected_markets: number;
};

export type HuijinEtfBaseline = {
  baseline_id: string;
  pool_version: string;
  symbol: string;
  name: string;
  index_name: string;
  role: HuijinEtfRole;
  paired_symbol: string | null;
  report_period: string;
  baseline_total_shares: number;
  confirmed_huijin_shares: number;
  confirmed_huijin_holding_pct: number;
  source_kind: HuijinBaselineSourceKind;
  source: string;
};

export type HuijinEtfActivityItem = {
  symbol: string;
  name: string;
  index_name: string;
  role: HuijinEtfRole;
  paired_symbol: string | null;
  trade_date: string;
  total_shares: number | null;
  previous_total_shares: number | null;
  share_delta: number | null;
  daily_change_pct: number | null;
  baseline_change_pct: number | null;
  cumulative_baseline_change_pct: number | null;
  multiple: number | null;
  direction: EtfActivityDirection;
  is_tenfold: boolean;
  report_period: string | null;
  baseline_total_shares: number | null;
  confirmed_huijin_shares: number | null;
  confirmed_huijin_holding_pct: number | null;
  baseline_source_kind: HuijinBaselineSourceKind | null;
};

export type HuijinEtfValidationGroup = {
  index_name: string;
  core_symbol: string;
  validator_symbol: string;
  state: EtfValidationState;
  conservative_daily_change_pct: number | null;
  conservative_baseline_change_pct: number | null;
  conservative_multiple: number | null;
};

export type HuijinEtfActivitySummary = {
  core_count: number;
  available_core_count: number;
  tenfold_increase_count: number;
  tenfold_decrease_count: number;
  confirmed_increase_group_count: number;
  confirmed_decrease_group_count: number;
  divergent_group_count: number;
  incomplete_group_count: number;
  strongest_symbol: string | null;
  strongest_baseline_change_pct: number | null;
};

export type EtfRadarSummary = {
  evidence_strength: number | null;
  evidence_level: CapitalEvidenceLevel | null;
  valid_etf_count: number;
  expected_etf_count: number;
  estimated_subscription_cny: number | null;
  evidence: string[];
  activity: HuijinEtfActivitySummary;
};

export type CapitalSummaryResponse = CapitalSignalMetadata & {
  margin: MarginSummary;
  etf_radar: EtfRadarSummary;
};

export type EtfRadarItem = {
  symbol: string;
  name: string;
  index_name: string;
  total_shares: number | null;
  share_change: number | null;
  estimated_subscription_cny: number | null;
  robust_score: number | null;
  same_time_turnover_ratio: number | null;
  relative_index_return_pct: number | null;
  late_session_acceleration: number | null;
  evidence_strength: number | null;
  evidence: string[];
};

export type EtfRadarOverviewResponse = CapitalSignalMetadata & {
  evidence_strength: number | null;
  evidence_level: CapitalEvidenceLevel | null;
  valid_etf_count: number;
  expected_etf_count: number;
  estimated_subscription_cny: number | null;
  evidence: string[];
  items: EtfRadarItem[];
  pool_version: string;
  baseline_version: string | null;
  baseline_fingerprint: string | null;
  activity: HuijinEtfActivitySummary;
  core_items: HuijinEtfActivityItem[];
  validation_items: HuijinEtfActivityItem[];
  validation_groups: HuijinEtfValidationGroup[];
};

export type EtfRadarHistoryPoint = {
  trade_date: string;
  symbol: string;
  name: string;
  total_shares: number | null;
  share_change: number | null;
  estimated_subscription_cny: number | null;
  robust_score: number | null;
  daily_change_pct: number | null;
  baseline_change_pct: number | null;
  cumulative_baseline_change_pct: number | null;
  multiple: number | null;
};

export type EtfRadarHistoryResponse = CapitalSignalMetadata & {
  points: EtfRadarHistoryPoint[];
};

export type EtfHolderPosition = {
  symbol: string;
  name: string;
  report_period: string;
  entity_name: string;
  shares: number | null;
  holding_pct: number | null;
  change_shares: number | null;
  source: string;
};

export type EtfRadarHoldersResponse = CapitalSignalMetadata & {
  positions: EtfHolderPosition[];
  baselines: HuijinEtfBaseline[];
};

export type EtfRadarFactorDefinition = {
  key: string;
  name: string;
  description: string;
  availability: string;
};

export type EtfRadarMethodologyResponse = CapitalSignalMetadata & {
  pool_version: string;
  core_pool: string[];
  thresholds: Record<string, number>;
  factors: EtfRadarFactorDefinition[];
  limitations: string[];
};

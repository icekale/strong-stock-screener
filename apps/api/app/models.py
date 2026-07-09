from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ScreenStatus = Literal["focus", "wait_pullback", "reduce_risk", "data_incomplete"]
RiskAction = Literal["hold_watch", "reduce", "empty"]
IntradayAction = Literal["watch", "low_buy_watch", "reduce", "avoid_chase", "data_incomplete"]
GsgfIntradayConfirmation = Literal["盘中确认", "等待确认", "低吸确认", "减仓确认", "风险失效", "无GSGF上下文"]
SourceStatusValue = Literal["success", "failed", "disabled", "missing_key", "stale"]
CapitalFlowStatus = Literal["direct", "estimated", "unavailable"]
SectorWorkbenchMode = Literal["strength", "main_flow"]
SectorWorkbenchScope = Literal["theme", "industry"]
SectorWorkbenchScopeRequest = Literal["theme", "industry", "auto"]
SectorFlowStatus = Literal["direct", "estimated", "unavailable"]
SectorReplicaMode = Literal["strength", "main_flow"]
IndustryStrength = Literal["strong", "neutral", "weak"]
RiskCheckStatus = Literal["triggered", "clear", "unknown"]
GsgfAction = Literal["strong_candidate", "watch_candidate", "wait_trigger", "avoid"]
GsgfFinalStatus = Literal["确认买点", "候选", "低吸观察", "观察", "减仓", "回避"]
GsgfZone = Literal["a_zone", "b_zone_a_point", "c_zone", "unformed", "unknown"]
GsgfVolumeStructure = Literal[
    "three_yang_controls_three_yin",
    "neutral",
    "three_yin_controls_three_yang",
    "unknown",
]
GsgfChartAnnotationType = Literal["volume_structure", "zone", "trigger", "pressure", "risk"]
GsgfChartAnnotationSeverity = Literal["positive", "neutral", "warning", "danger"]
ScreenStrategy = Literal["strong_stock", "gsgf", "combined"]
ShortTermAlertSeverity = Literal["high", "medium", "low"]
MarketEmotionLevel = Literal["冰点", "一般", "良好", "火爆"]
SentimentSnapshotStatus = Literal["fresh", "cached", "missing"]
SentimentMarketState = Literal["冰点", "修复", "主升", "高潮", "分歧", "退潮"]
SentimentTradePermission = Literal["空仓等待", "轻仓试错", "强势进攻", "只低吸", "只卖不追"]
SentimentRiskLevel = Literal["低", "中", "高"]
SentimentWatchlistAction = Literal["重点盯", "等确认", "风险回避"]
BackgroundJobStatus = Literal["pending", "running", "success", "failed", "canceled"]
AuctionModelBucket = Literal["selected", "attack", "watch", "avoid"]
AuctionModelCacheStatus = Literal["generated", "cached"]
AuctionTop3EntryPolicy = Literal["open_0930", "after_0935_confirm", "before_1000_strength", "close_follow"]
AuctionTop3ExitPolicy = Literal[
    "intraday_stop",
    "intraday_take_profit",
    "close_exit",
    "next_open_exit",
    "next_close_exit",
]
AuctionTop3TradeLabel = Literal["win", "loss", "neutral", "data_incomplete"]
AuctionReviewStatus = Literal["pending", "intraday_done", "day_done", "next_day_done", "data_incomplete"]
ModelMaintenanceProvider = Literal["openai", "deepseek", "openai_compatible"]
ModelMaintenanceHealthStatus = Literal[
    "normal",
    "watch",
    "degraded",
    "insufficient_sample",
    "data_unreliable",
]
ModelMaintenanceRuleStatus = Literal[
    "effective",
    "neutral",
    "over_strict",
    "under_strict",
    "degraded",
    "insufficient_sample",
]
ModelMaintenanceSuggestionType = Literal[
    "observe",
    "adjust_weight",
    "loosen_filter",
    "tighten_filter",
    "disable_rule_temporarily",
    "data_check",
]
ModelMaintenanceSuggestionStatus = Literal["pending", "accepted", "ignored", "snoozed"]
HeatmapPeriodKey = Literal["day", "week", "month", "year"]
HeatmapMarketKey = Literal["all", "sse", "szse", "hs300", "zza500", "cyb", "kcb"]
HeatmapSizeMode = Literal["market_cap", "turnover"]
HeatmapTrendFilter = Literal["all", "rise", "fall"]
HeatmapExchange = Literal["SH", "SZ", "BJ"]


class GsgfScoreBreakdown(BaseModel):
    safety_pressure: int = 0
    volume_thickness: int = 0
    ma_alignment: int = 0
    pattern_space: int = 0
    star_trigger: int = 0
    sector_theme: int = 0


class GsgfTradePlan(BaseModel):
    status: GsgfFinalStatus
    holder_guidance: list[str] = Field(default_factory=list)
    empty_position_guidance: list[str] = Field(default_factory=list)
    risk_invalidation: list[str] = Field(default_factory=list)
    research_note: str = "规则解释仅作研究辅助，不构成收益承诺或投资建议。"


class GsgfAnalysis(BaseModel):
    model_version: str = "gsgf-v2"
    total_score: int = 0
    action: GsgfAction = "wait_trigger"
    final_status: GsgfFinalStatus = "观察"
    zone: GsgfZone = "unknown"
    volume_structure: GsgfVolumeStructure = "unknown"
    setup_type: str | None = None
    setup_score: int = 0
    confirm_type: str | None = None
    confirm_score: int = 0
    scores: GsgfScoreBreakdown = Field(default_factory=GsgfScoreBreakdown)
    pattern_tags: list[str] = Field(default_factory=list)
    trigger_tags: list[str] = Field(default_factory=list)
    pressure_flags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)
    trade_plan: GsgfTradePlan | None = None


class GsgfChartAnnotation(BaseModel):
    type: GsgfChartAnnotationType
    label: str
    description: str
    severity: GsgfChartAnnotationSeverity = "neutral"
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    price: float | None = None


class StrongStockCandidate(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    total_market_cap_cny: float | None = None
    circulating_market_cap_cny: float | None = None
    limit_up_evidence: list[str] = Field(default_factory=list)
    board_note: str | None = None
    abnormal_status: RiskCheckStatus = "unknown"
    abnormal_flags: list[str] = Field(default_factory=list)


class KlineBar(BaseModel):
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None


class StrongStockScreeningItem(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    industry_strength: IndustryStrength | None = None
    industry_score: int = 0
    industry_rank: int | None = None
    industry_notes: list[str] = Field(default_factory=list)
    status: ScreenStatus
    score: int
    rule_hits: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    severe_abnormal_warning: RiskCheckStatus = "unknown"
    negative_news_status: RiskCheckStatus = "unknown"
    negative_news_flags: list[str] = Field(default_factory=list)
    intraday_notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    data_status: Literal["complete", "incomplete"] = "complete"
    source_trace: list[str] = Field(default_factory=list)
    gsgf: GsgfAnalysis | None = None


class StrongStockRiskItem(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    risk_action: RiskAction
    risk_flags: list[str] = Field(default_factory=list)
    severe_abnormal_warning: RiskCheckStatus = "unknown"
    negative_news_status: RiskCheckStatus = "unknown"
    negative_news_flags: list[str] = Field(default_factory=list)
    intraday_notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_trace: list[str] = Field(default_factory=list)
    gsgf: GsgfAnalysis | None = None


class StrongStockIntradayItem(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    action: IntradayAction
    group: str | None = None
    tags: list[str] = Field(default_factory=list)
    last_price: float | None = None
    pct_change: float | None = None
    open_gap_pct: float | None = None
    intraday_ma: float | None = None
    latest_vs_intraday_ma_pct: float | None = None
    volume: float | None = None
    turnover_cny: float | None = None
    gsgf_intraday_confirmation: GsgfIntradayConfirmation = "无GSGF上下文"
    signals: list[str] = Field(default_factory=list)
    source_trace: list[str] = Field(default_factory=list)


class StrongStockSourceStatus(BaseModel):
    source: str
    status: SourceStatusValue
    detail: str


class HeatmapStockNode(BaseModel):
    symbol: str
    code: str
    name: str
    industry: str
    sub_industry: str | None = None
    exchange: HeatmapExchange
    market: HeatmapMarketKey
    price: float | None = None
    change_pct: float = 0
    week_change_pct: float | None = None
    month_change_pct: float | None = None
    year_change_pct: float | None = None
    turnover_cny: float | None = None
    circulating_market_cap_cny: float | None = None
    total_market_cap_cny: float | None = None
    value: float = 0
    quote_time: str | None = None


class HeatmapBoardNode(BaseModel):
    key: str
    name: str
    value: float = 0
    stock_count: int = 0
    advance_count: int = 0
    decline_count: int = 0
    unchanged_count: int = 0
    avg_change_pct: float | None = None
    turnover_cny: float | None = None
    children: list[HeatmapStockNode] = Field(default_factory=list)


class HeatmapSummary(BaseModel):
    trade_date: str | None = None
    updated_at: str
    stock_count: int = 0
    board_count: int = 0
    advance_count: int = 0
    decline_count: int = 0
    unchanged_count: int = 0
    turnover_cny: float | None = None
    previous_turnover_cny: float | None = None
    turnover_change_pct: float | None = None
    index_change_pct: float | None = None


class HeatmapTreemapResponse(BaseModel):
    market: HeatmapMarketKey
    period: HeatmapPeriodKey
    size_mode: HeatmapSizeMode
    trend: HeatmapTrendFilter = "all"
    board: str | None = None
    summary: HeatmapSummary
    nodes: list[HeatmapBoardNode] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str


class HeatmapQuoteItem(BaseModel):
    symbol: str
    price: float | None = None
    change_pct: float = 0
    turnover_cny: float | None = None
    quote_time: str | None = None


class HeatmapQuotesResponse(BaseModel):
    market: HeatmapMarketKey
    period: HeatmapPeriodKey
    quotes: dict[str, HeatmapQuoteItem] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str


class HeatmapOverviewItem(BaseModel):
    market: HeatmapMarketKey
    name: str
    change_pct: float | None = None
    stock_count: int = 0
    updated_at: str


class HeatmapOverviewResponse(BaseModel):
    period: HeatmapPeriodKey
    markets: list[HeatmapOverviewItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str


class AuctionReviewSnapshot(BaseModel):
    open_gap_pct: float | None = None
    current_pct_change: float | None = None
    turnover_rate: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    auction_score: float = 0
    rank: int | None = None
    tier: str = "neutral"
    signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    quote_time: str | None = None


class AuctionReviewOutcome(BaseModel):
    peak_pct: float | None = None
    close_pct: float | None = None
    drawdown_pct: float | None = None
    limit_up: bool | None = None
    open_pct: float | None = None
    strong_follow: bool | None = None
    status: str = "pending"


class AuctionReviewScore(BaseModel):
    intraday_score: float | None = None
    day_score: float | None = None
    next_day_score: float | None = None
    total_score: float | None = None


class AuctionReviewRecord(BaseModel):
    trade_date: str
    symbol: str
    name: str | None = None
    industry: str | None = None
    selected_at_label: str = "manual"
    selected_at: str | None = None
    auction_snapshot: AuctionReviewSnapshot = Field(default_factory=AuctionReviewSnapshot)
    rule_tags: list[str] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    intraday_result: AuctionReviewOutcome = Field(default_factory=AuctionReviewOutcome)
    day_result: AuctionReviewOutcome = Field(default_factory=AuctionReviewOutcome)
    next_day_result: AuctionReviewOutcome = Field(default_factory=AuctionReviewOutcome)
    score: AuctionReviewScore = Field(default_factory=AuctionReviewScore)
    review_status: AuctionReviewStatus = "pending"


class AuctionRuleBucket(BaseModel):
    rule_tag: str
    sample_count: int = 0
    win_rate: float | None = None
    avg_score: float | None = None
    avg_intraday_peak_pct: float | None = None
    avg_close_pct: float | None = None
    avg_next_open_pct: float | None = None
    avg_drawdown_pct: float | None = None
    failure_count: int = 0
    suggestion: str = "样本不足，不建议调整。"


class AuctionReviewSummary(BaseModel):
    trade_date: str | None = None
    record_count: int = 0
    pending_count: int = 0
    completed_count: int = 0
    data_incomplete_count: int = 0
    records: list[AuctionReviewRecord] = Field(default_factory=list)
    buckets: list[AuctionRuleBucket] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class AuctionBackfillResponse(BaseModel):
    status: str = "data_unavailable"
    saved_count: int = 0
    message: str = "历史集合竞价数据源尚未验证，未生成回填样本。"


class StockQuoteResponse(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    last_price: float | None = None
    prev_close: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    pct_change: float | None = None
    turnover_rate: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    quote_time: str | None = None
    total_market_cap_cny: float | None = None
    circulating_market_cap_cny: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    valuation_source_status: StrongStockSourceStatus | None = None
    source_status: StrongStockSourceStatus


class GsgfBacktestWindowStat(BaseModel):
    window_days: int
    sample_count: int = 0
    win_rate: float | None = None
    avg_return_pct: float | None = None
    median_return_pct: float | None = None
    avg_max_drawdown_pct: float | None = None


class GsgfBacktestBucket(BaseModel):
    status: GsgfFinalStatus
    sample_count: int = 0
    avg_score: float | None = None
    windows: list[GsgfBacktestWindowStat] = Field(default_factory=list)


class GsgfBacktestSummary(BaseModel):
    windows: list[int] = Field(default_factory=list)
    sample_count: int = 0
    buckets: list[GsgfBacktestBucket] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class GsgfReviewRecord(BaseModel):
    trade_date: str
    symbol: str
    name: str
    signal_type: str
    status: GsgfFinalStatus
    score: int
    setup_type: str | None = None
    confirm_type: str | None = None


class GsgfReviewSnapshotResponse(BaseModel):
    saved_count: int = 0
    records: list[GsgfReviewRecord] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class GsgfReviewWindowResult(BaseModel):
    window_days: int
    realized_return_pct: float | None = None
    max_drawdown_pct: float | None = None


class GsgfReviewItem(BaseModel):
    record: GsgfReviewRecord
    confirmed: bool = False
    windows: list[GsgfReviewWindowResult] = Field(default_factory=list)


class GsgfReviewBucket(BaseModel):
    signal_type: str
    status: GsgfFinalStatus
    sample_count: int = 0
    confirmed_count: int = 0
    avg_return_pct: float | None = None
    avg_max_drawdown_pct: float | None = None


class GsgfReviewSummary(BaseModel):
    windows: list[int] = Field(default_factory=list)
    record_count: int = 0
    items: list[GsgfReviewItem] = Field(default_factory=list)
    buckets: list[GsgfReviewBucket] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class GsgfCalibrationExample(BaseModel):
    trade_date: str
    symbol: str
    name: str
    status: GsgfFinalStatus
    score: int
    setup_type: str | None = None
    confirm_type: str | None = None
    entry_close: float | None = None


class GsgfCalibrationWindowStat(BaseModel):
    window_days: int
    sample_count: int = 0
    hit_count: int = 0
    hit_rate: float | None = None
    avg_return_pct: float | None = None
    avg_max_drawdown_pct: float | None = None


class GsgfCalibrationSampleWindow(BaseModel):
    window_days: int
    realized_return_pct: float | None = None
    max_drawdown_pct: float | None = None


class GsgfCalibrationSample(BaseModel):
    trade_date: str
    symbol: str
    name: str
    status: GsgfFinalStatus
    score: int
    setup_type: str | None = None
    confirm_type: str | None = None
    zone: GsgfZone = "unknown"
    bucket_names: list[str] = Field(default_factory=list)
    entry_close: float | None = None
    windows: list[GsgfCalibrationSampleWindow] = Field(default_factory=list)


class GsgfCalibrationBucket(BaseModel):
    name: str
    sample_count: int = 0
    composite_score: float | None = None
    calibration_rating: str = "样本不足"
    windows: list[GsgfCalibrationWindowStat] = Field(default_factory=list)
    examples: list[GsgfCalibrationExample] = Field(default_factory=list)


class GsgfCalibrationDiagnosticGroup(BaseModel):
    name: str
    buckets: list[GsgfCalibrationBucket] = Field(default_factory=list)


class GsgfRealCalibrationSummary(BaseModel):
    trade_dates: list[str] = Field(default_factory=list)
    windows: list[int] = Field(default_factory=list)
    scanned_count: int = 0
    target_sample_count: int = 0
    skipped_count: int = 0
    buckets: list[GsgfCalibrationBucket] = Field(default_factory=list)
    unique_symbol_buckets: list[GsgfCalibrationBucket] = Field(default_factory=list)
    diagnostic_groups: list[GsgfCalibrationDiagnosticGroup] = Field(default_factory=list)
    samples: list[GsgfCalibrationSample] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class BackgroundJobState(BaseModel):
    job_id: str
    type: str
    status: BackgroundJobStatus = "pending"
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result_path: str | None = None
    result: dict[str, Any] | None = None


class GsgfModelHealth(BaseModel):
    best_signals: list[str] = Field(default_factory=list)
    weak_signals: list[str] = Field(default_factory=list)
    insufficient_sample_signals: list[str] = Field(default_factory=list)
    degraded_signals: list[str] = Field(default_factory=list)
    last_review_at: str | None = None
    last_calibration_at: str | None = None
    summary_text: str = "仅供复盘与模型校准，不构成投资建议。"


class ModelMaintenanceSuggestion(BaseModel):
    suggestion_id: str
    type: ModelMaintenanceSuggestionType = "observe"
    title: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    risk: str = "仅供模型维护参考，不构成投资建议。"
    confidence: float = Field(default=0, ge=0, le=1)
    suggested_action: str = "观察，不自动调整。"
    status: ModelMaintenanceSuggestionStatus = "pending"


class ModelMaintenanceRuleDiagnostic(BaseModel):
    rule_name: str
    status: ModelMaintenanceRuleStatus = "neutral"
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)


class ModelMaintenancePacket(BaseModel):
    packet_id: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )
    trade_date: str | None = None
    model_name: str = "gsgf"
    model_version: str | None = None
    screen_strategy: str | None = None
    screen_params: dict[str, Any] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    latest_screen_run: dict[str, Any] = Field(default_factory=dict)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    calibration_summary: dict[str, Any] = Field(default_factory=dict)
    false_negative_cases: list[dict[str, Any]] = Field(default_factory=list)
    false_positive_cases: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    model_sections: dict[str, Any] = Field(default_factory=dict)
    packet_url: str | None = None


class ModelMaintenanceReport(BaseModel):
    report_id: str
    packet_id: str
    provider: ModelMaintenanceProvider = "openai_compatible"
    model: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )
    health_status: ModelMaintenanceHealthStatus = "insufficient_sample"
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    rule_diagnostics: list[ModelMaintenanceRuleDiagnostic] = Field(default_factory=list)
    suggestions: list[ModelMaintenanceSuggestion] = Field(default_factory=list)
    disclaimer: str = "仅供模型复盘与参数维护参考，不构成投资建议。"


class MarketTurnoverSummary(BaseModel):
    total_cny: float | None = None
    previous_total_cny: float | None = None
    change_cny: float | None = None
    change_pct: float | None = None


class MarketAdvanceDeclineSummary(BaseModel):
    advance_count: int | None = None
    decline_count: int | None = None
    unchanged_count: int | None = None
    limit_up_count: int | None = None
    limit_down_count: int | None = None


class MarketSectorStrengthItem(BaseModel):
    name: str
    change_pct: float | None = None
    turnover_cny: float | None = None
    advance_count: int | None = None
    decline_count: int | None = None
    leader: str | None = None
    source: str


class MarketIndexSnapshot(BaseModel):
    symbol: str
    name: str
    last_price: float | None = None
    change_pct: float | None = None
    turnover_cny: float | None = None
    source: str


class MarketOverviewResponse(BaseModel):
    trade_date: str | None = None
    turnover: MarketTurnoverSummary = Field(default_factory=MarketTurnoverSummary)
    advance_decline: MarketAdvanceDeclineSummary = Field(
        default_factory=MarketAdvanceDeclineSummary
    )
    indices: list[MarketIndexSnapshot] = Field(default_factory=list)
    sectors: list[MarketSectorStrengthItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class MarketRankingItem(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    last_price: float | None = None
    pct_change: float | None = None
    current_pct_change: float | None = None
    open_price: float | None = None
    prev_close: float | None = None
    turnover_rate: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    quote_time: str | None = None


class MarketRankingsResponse(BaseModel):
    trade_date: str | None = None
    pct_change_rank: list[MarketRankingItem] = Field(default_factory=list)
    turnover_rank: list[MarketRankingItem] = Field(default_factory=list)
    buckets: list["MarketEmotionBucket"] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class AuctionSnapshotMetrics(BaseModel):
    candidate_count: int = 0
    strong_high_open_count: int = 0
    high_risk_count: int = 0
    total_turnover_cny: float | None = None


class AuctionSnapshotItem(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    themes: list[str] = Field(default_factory=list)
    hot_theme_rank: int | None = None
    hot_theme_score: float | None = None
    theme_auction_rank: int | None = None
    theme_resonance: bool = False
    last_price: float | None = None
    current_pct_change: float | None = None
    open_gap_pct: float | None = None
    turnover_rate: float | None = None
    turnover_cny: float | None = None
    volume: float | None = None
    auction_score: float = 0
    tier: str = "neutral"
    action_note: str | None = None
    signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    quote_time: str | None = None


class AuctionSnapshotResponse(BaseModel):
    trade_date: str | None = None
    session: str = "unknown"
    snapshot_status: str = "fresh"
    cache_age_seconds: float | None = None
    metrics: AuctionSnapshotMetrics = Field(default_factory=AuctionSnapshotMetrics)
    items: list[AuctionSnapshotItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class AuctionTimelinePoint(BaseModel):
    label: str
    target_time: str
    snapshot_status: str = "waiting"
    captured_at: str | None = None
    metrics: AuctionSnapshotMetrics = Field(default_factory=AuctionSnapshotMetrics)
    items: list[AuctionSnapshotItem] = Field(default_factory=list)


class AuctionTimelineResponse(BaseModel):
    points: list[AuctionTimelinePoint] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class AuctionModelPredictionItem(BaseModel):
    symbol: str
    name: str = ""
    prob_3pct: float
    bucket: AuctionModelBucket = "watch"
    rank: int | None = None
    prev_close_price: float | None = None
    market_cap_float: float | None = None
    avg_amount_3d: float | None = None
    feature_end_date: str | None = None
    guard_rule: str | None = None
    strategy_note: str | None = None
    trend_reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    data_quality: list[str] = Field(default_factory=list)


class AuctionModelBacktestSummary(BaseModel):
    period: list[str] = Field(default_factory=list)
    sample_count: int = 0
    win_rate: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    payoff_ratio: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    average_return: float | None = None
    breakeven_win_rate: float | None = None
    capital_return_pct: float | None = None


class AuctionModelTop3Response(BaseModel):
    run_id: str = Field(default_factory=lambda: datetime.now().astimezone().strftime("%Y%m%d%H%M%S%f"))
    trade_date: str
    feature_end_date: str
    model_version: str
    feature_version: str
    guard_rule: str
    mode: str = "research_live_signal"
    cache_status: AuctionModelCacheStatus = "generated"
    backtest: AuctionModelBacktestSummary | None = None
    items: list[AuctionModelPredictionItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


AuctionTop3LiveConfirmation = Literal["buyable", "watch", "reject"]


class AuctionTop3RealtimeSnapshot(BaseModel):
    last_price: float | None = None
    current_pct_change: float | None = None
    open_gap_pct: float | None = None
    turnover_cny: float | None = None
    turnover_rate: float | None = None
    quote_time: str | None = None


class AuctionTop3LiveConfirmationItem(BaseModel):
    symbol: str
    name: str = ""
    model_rank: int | None = None
    model_bucket: AuctionModelBucket = "watch"
    prob_3pct: float
    confirmation: AuctionTop3LiveConfirmation
    realtime: AuctionTop3RealtimeSnapshot | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    data_quality: list[str] = Field(default_factory=list)


class AuctionTop3LiveConfirmationResponse(BaseModel):
    trade_date: str
    model_run_id: str | None = None
    cache_status: AuctionModelCacheStatus = "cached"
    items: list[AuctionTop3LiveConfirmationItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class AuctionTop3SignalSample(BaseModel):
    sample_id: str
    trade_date: str
    symbol: str
    name: str = ""
    industry: str | None = None
    rank: int | None = None
    score: float = 0
    model_version: str
    feature_version: str
    guard_rule: str | None = None
    signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    feature_snapshot: dict[str, Any] = Field(default_factory=dict)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3SimulatedTradeSample(BaseModel):
    sample_id: str
    signal_sample_id: str
    portfolio_id: str = "default"
    trade_date: str
    symbol: str
    entry_policy: AuctionTop3EntryPolicy
    entry_price: float | None = None
    entry_time: str | None = None
    exit_policy: AuctionTop3ExitPolicy
    exit_price: float | None = None
    exit_time: str | None = None
    position_pct: float = 0.33
    return_pct: float | None = None
    profit_amount: float | None = None
    max_drawdown_pct: float | None = None
    max_favorable_pct: float | None = None
    label: AuctionTop3TradeLabel = "data_incomplete"
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))

    @model_validator(mode="after")
    def infer_label_from_return(self) -> "AuctionTop3SimulatedTradeSample":
        if self.return_pct is None:
            return self
        if self.return_pct > 0:
            self.label = "win"
        elif self.return_pct < 0:
            self.label = "loss"
        else:
            self.label = "neutral"
        return self


class AuctionTop3SimulatedPerformancePoint(BaseModel):
    portfolio_id: str = "default"
    trade_date: str
    entry_policy: AuctionTop3EntryPolicy
    exit_policy: AuctionTop3ExitPolicy
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    daily_return_pct: float | None = None
    cumulative_return_pct: float | None = None
    equity: float | None = None
    max_drawdown_pct: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3ManualTradeSample(BaseModel):
    sample_id: str
    signal_sample_id: str
    trade_date: str
    symbol: str
    enabled_for_training: bool = False
    bought: bool = False
    buy_price: float | None = None
    sell_price: float | None = None
    position_pct: float | None = None
    buy_reason: str = ""
    sell_reason: str = ""
    return_pct: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class AuctionTop3TrainingSummary(BaseModel):
    enabled: bool = True
    signal_sample_count: int = 0
    simulated_trade_sample_count: int = 0
    manual_trade_sample_count: int = 0
    date_range: list[str] = Field(default_factory=list)
    training_window_days: int = 60
    latest_generated_at: str | None = None
    simulated_profit_summary: dict[str, Any] = Field(default_factory=dict)
    quality_notes: list[str] = Field(default_factory=list)


class AuctionTop3PerformanceResponse(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    points: list[AuctionTop3SimulatedPerformancePoint] = Field(default_factory=list)
    trades: list[AuctionTop3SimulatedTradeSample] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


class SectorRadarItem(BaseModel):
    name: str
    source: str
    change_pct: float | None = None
    turnover_cny: float | None = None
    advance_count: int | None = None
    decline_count: int | None = None
    leader: str | None = None
    net_flow_cny: float | None = None
    strength_score: float = 0


class SectorRadarResponse(BaseModel):
    trade_date: str | None = None
    capital_flow_status: CapitalFlowStatus = "unavailable"
    flow_source: str
    inflow: list[SectorRadarItem] = Field(default_factory=list)
    outflow: list[SectorRadarItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SectorWorkbenchTheme(BaseModel):
    name: str
    scope: SectorWorkbenchScope
    limit_up_count: int = 0
    strength_score: float = 0
    main_flow_cny: float | None = None
    turnover_cny: float | None = None
    change_pct: float | None = None
    leader: str | None = None
    member_count: int = 0
    source: str
    flow_status: SectorFlowStatus = "unavailable"


class SectorWorkbenchPoint(BaseModel):
    time: str
    value: float
    sampled_at: str


class SectorWorkbenchSeries(BaseModel):
    name: str
    scope: SectorWorkbenchScope
    metric: SectorWorkbenchMode
    points: list[SectorWorkbenchPoint] = Field(default_factory=list)


class SectorWorkbenchStock(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    themes: list[str] = Field(default_factory=list)
    pct_change: float | None = None
    turnover_cny: float | None = None
    turnover_rate: float | None = None
    limit_up: bool = False
    board_count: int = 0
    auction_pct_change: float | None = None
    auction_turnover_cny: float | None = None
    seal_amount_cny: float | None = None
    risk_flags: list[str] = Field(default_factory=list)


class SectorWorkbenchResponse(BaseModel):
    scope: SectorWorkbenchScope
    mode: SectorWorkbenchMode
    trade_date: str | None = None
    themes: list[SectorWorkbenchTheme] = Field(default_factory=list)
    selected_themes: list[str] = Field(default_factory=list)
    series: list[SectorWorkbenchSeries] = Field(default_factory=list)
    related_tags: list[str] = Field(default_factory=list)
    stocks: list[SectorWorkbenchStock] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SectorReplicaPlate(BaseModel):
    code: str
    name: str
    val: float
    ztcount: int = 0
    display_value: str | None = None


class SectorReplicaChartSeries(BaseModel):
    name: str
    type: str = "line"
    data: list[float | None] = Field(default_factory=list)
    smooth: bool = True
    showSymbol: bool = False


class SectorReplicaQxLive(BaseModel):
    Aaxis: list[str] = Field(default_factory=list)
    zflist: list[float] = Field(default_factory=list)
    series: dict[str, list[float | None]] = Field(default_factory=dict)


class SectorReplicaStockRow(BaseModel):
    symbol: str
    code: str
    name: str | None = None
    pct_change: float | None = None
    turnover_cny: float | None = None
    circulating_value_cny: float | None = None
    board_label: str = "--"
    auction_pct_change: float | None = None
    auction_amount_cny: float | None = None
    auction_volume_ratio: float | None = None
    buy_ratio_pct: float | None = None
    seal_amount_cny: float | None = None
    leader_tag: str | None = None
    themes: list[str] = Field(default_factory=list)
    industry: str | None = None
    compat_row: list[Any] = Field(default_factory=list)


class SectorReplicaStocksResponse(BaseModel):
    board_code: str | None = None
    sub_theme: str | None = None
    rows: list[SectorReplicaStockRow] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SectorReplicaRadarResponse(BaseModel):
    result: str = "success"
    mode: SectorReplicaMode
    trade_date: str | None = None
    axis: list[str] = Field(default_factory=list)
    qxlive: SectorReplicaQxLive = Field(default_factory=SectorReplicaQxLive)
    plates: list[SectorReplicaPlate] = Field(default_factory=list)
    checkplate: list[str] = Field(default_factory=list)
    legend: list[str] = Field(default_factory=list)
    series: list[SectorReplicaChartSeries] = Field(default_factory=list)
    stocks: list[SectorReplicaStockRow] = Field(default_factory=list)
    related_tags: list[str] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SectorWorkbenchCacheSummary(BaseModel):
    trade_date: str | None = None
    sample_count: int = 0
    latest_sampled_at: str | None = None
    modes: list[SectorWorkbenchMode] = Field(default_factory=list)
    scopes: list[SectorWorkbenchScope] = Field(default_factory=list)
    metrics: list[SectorWorkbenchMode] = Field(default_factory=list)
    sample_sources: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)


class SectorWorkbenchStatusResponse(BaseModel):
    trade_date: str
    sample_window_open: bool = False
    sampler_enabled: bool = False
    sampler_running: bool = False
    interval_seconds: float | None = None
    idle_seconds: float | None = None
    cache: SectorWorkbenchCacheSummary = Field(default_factory=SectorWorkbenchCacheSummary)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


SystemConfidence = Literal["fresh", "stale", "partial", "degraded", "unavailable"]


class SystemCacheItem(BaseModel):
    name: str
    group: str
    ttl_seconds: float
    size: int
    fresh_count: int
    refreshing_count: int
    hits: int
    misses: int
    stale_hits: int
    refresh_count: int
    refresh_error_count: int
    last_refresh_started_at: float | None = None
    last_refresh_finished_at: float | None = None
    last_error: str | None = None
    oldest_expires_in_seconds: float | None = None


class SystemCacheSummary(BaseModel):
    total: int
    items: list[SystemCacheItem] = Field(default_factory=list)


class SystemJobStatus(BaseModel):
    name: str
    running: bool
    enabled: bool
    detail: str


class SystemStatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    generated_at: str
    cache: SystemCacheSummary
    jobs: list[SystemJobStatus] = Field(default_factory=list)
    confidence: SystemConfidence = "fresh"


class SystemCacheClearResponse(BaseModel):
    cleared: list[str] = Field(default_factory=list)


class ShortTermSentimentStockItem(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    board_count: int = 1
    limit_up_hits_20d: int = 0
    break_board_count: int = 0
    last_limit_up_date: str | None = None
    first_seal_time: str | None = None
    last_seal_time: str | None = None
    board_note: str | None = None
    limit_up_evidence: list[str] = Field(default_factory=list)


class ShortTermSentimentLadderGroup(BaseModel):
    board_count: int
    label: str
    items: list[ShortTermSentimentStockItem] = Field(default_factory=list)


class ShortTermSentimentIndustryItem(BaseModel):
    name: str
    limit_up_count: int = 0
    break_board_count: int = 0
    max_consecutive_boards: int = 0
    leader: str | None = None
    symbols: list[str] = Field(default_factory=list)
    strength_score: float = 0


class ShortTermSentimentMetrics(BaseModel):
    limit_up_count: int = 0
    break_board_count: int = 0
    max_consecutive_boards: int = 0
    hot_industry_count: int = 0


class ShortTermSentimentResponse(BaseModel):
    trade_date: str
    metrics: ShortTermSentimentMetrics = Field(default_factory=ShortTermSentimentMetrics)
    limit_up_pool: list[ShortTermSentimentStockItem] = Field(default_factory=list)
    break_board_pool: list[ShortTermSentimentStockItem] = Field(default_factory=list)
    ladder: list[ShortTermSentimentLadderGroup] = Field(default_factory=list)
    hot_industries: list[ShortTermSentimentIndustryItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class ShortTermIntradaySentimentItem(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    pool_tags: list[str] = Field(default_factory=list)
    action: IntradayAction
    last_price: float | None = None
    pct_change: float | None = None
    open_gap_pct: float | None = None
    intraday_ma: float | None = None
    latest_vs_intraday_ma_pct: float | None = None
    turnover_cny: float | None = None
    signals: list[str] = Field(default_factory=list)


class ShortTermIntradaySentimentMetrics(BaseModel):
    watched_count: int = 0
    alert_count: int = 0
    reduce_count: int = 0
    low_buy_watch_count: int = 0
    avoid_chase_count: int = 0


class ShortTermIntradaySentimentResponse(BaseModel):
    trade_date: str
    metrics: ShortTermIntradaySentimentMetrics = Field(
        default_factory=ShortTermIntradaySentimentMetrics
    )
    items: list[ShortTermIntradaySentimentItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class ShortTermIntradaySignalAlert(BaseModel):
    symbol: str
    name: str
    industry: str | None = None
    action: IntradayAction
    severity: ShortTermAlertSeverity
    pool_tags: list[str] = Field(default_factory=list)
    pct_change: float | None = None
    turnover_cny: float | None = None
    reasons: list[str] = Field(default_factory=list)


class ShortTermIntradaySignalDigest(BaseModel):
    title: str
    trade_date: str
    alert_count: int = 0
    alerts: list[ShortTermIntradaySignalAlert] = Field(default_factory=list)
    message_text: str
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class MarketEmotionBucket(BaseModel):
    label: str
    min_pct: float | None = None
    max_pct: float | None = None
    count: int | None = None
    source: str = "待接入全市场实时涨跌幅分布"


class MarketEmotionMetrics(BaseModel):
    emotion_score: float = 0
    emotion_level: MarketEmotionLevel = "冰点"
    limit_up_count: int = 0
    break_board_count: int = 0
    limit_down_count: int | None = None
    losing_effect_score: float | None = None
    max_consecutive_boards: int = 0
    advance_count: int | None = None
    decline_count: int | None = None
    seal_rate_pct: float | None = None
    turnover_cny: float | None = None
    turnover_change_cny: float | None = None
    turnover_change_pct: float | None = None
    main_flow_cny: float | None = None
    yesterday_limit_up_performance_pct: float | None = None
    yesterday_ladder_performance_pct: float | None = None


class MarketEmotionSample(BaseModel):
    trade_date: str
    sampled_at: str
    emotion_score: float = 0
    emotion_level: MarketEmotionLevel = "冰点"
    limit_up_count: int = 0
    break_board_count: int = 0
    limit_down_count: int | None = None
    losing_effect_score: float | None = None
    max_consecutive_boards: int = 0
    advance_count: int | None = None
    decline_count: int | None = None
    seal_rate_pct: float | None = None
    turnover_cny: float | None = None
    turnover_change_pct: float | None = None


class MarketEmotionSnapshotResponse(BaseModel):
    trade_date: str
    metrics: MarketEmotionMetrics = Field(default_factory=MarketEmotionMetrics)
    buckets: list[MarketEmotionBucket] = Field(default_factory=list)
    samples: list[MarketEmotionSample] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SentimentSummaryMetrics(BaseModel):
    emotion_score: float = 0
    emotion_level: MarketEmotionLevel = "冰点"
    limit_up_count: int = 0
    break_board_count: int = 0
    limit_down_count: int | None = None
    losing_effect_score: float | None = None
    max_consecutive_boards: int = 0
    advance_count: int | None = None
    decline_count: int | None = None
    seal_rate_pct: float | None = None
    turnover_cny: float | None = None
    turnover_change_cny: float | None = None
    turnover_change_pct: float | None = None


class SentimentSummaryResponse(BaseModel):
    trade_date: str
    snapshot_status: SentimentSnapshotStatus = "fresh"
    cached_at: str | None = None
    metrics: SentimentSummaryMetrics = Field(default_factory=SentimentSummaryMetrics)
    hot_industries: list[ShortTermSentimentIndustryItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SentimentMainSectorSignal(BaseModel):
    name: str
    strength_score: float = 0
    limit_up_count: int = 0
    break_board_count: int = 0
    max_consecutive_boards: int = 0
    leader: str | None = None
    symbols: list[str] = Field(default_factory=list)


class SentimentDecisionResponse(BaseModel):
    trade_date: str
    market_state: SentimentMarketState = "冰点"
    trade_permission: SentimentTradePermission = "空仓等待"
    risk_level: SentimentRiskLevel = "中"
    confidence: float = Field(default=0, ge=0, le=100)
    score_change: float | None = None
    main_sectors: list[SentimentMainSectorSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class SentimentDecisionOutcome(BaseModel):
    trade_date: str
    next_day_index_pct: float | None = None
    next_day_limit_up_count: int | None = None
    next_day_limit_down_count: int | None = None
    hit: bool = False
    score: float = 0
    reason: str = ""


class SentimentReviewSummary(BaseModel):
    trade_date: str
    sample_count: int = 0
    hit_count: int = 0
    hit_rate_pct: float = 0
    avg_score: float = 0
    outcomes: list[SentimentDecisionOutcome] = Field(default_factory=list)


class SentimentWatchlistAlert(BaseModel):
    symbol: str
    name: str
    group: str | None = None
    tags: list[str] = Field(default_factory=list)
    action: SentimentWatchlistAction = "等确认"
    matched_sector: str | None = None
    reasons: list[str] = Field(default_factory=list)


class SentimentDetailResponse(BaseModel):
    trade_date: str
    snapshot_status: SentimentSnapshotStatus = "fresh"
    cached_at: str | None = None
    sentiment: ShortTermSentimentResponse
    market_emotion: MarketEmotionSnapshotResponse


class StockKlineResponse(BaseModel):
    symbol: str
    source_status: StrongStockSourceStatus
    bars: list[KlineBar] = Field(default_factory=list)
    gsgf_annotations: list[GsgfChartAnnotation] = Field(default_factory=list)


class StockResearchResponse(BaseModel):
    symbol: str
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    profile: dict[str, Any] = Field(default_factory=dict)
    valuation: dict[str, Any] = Field(default_factory=dict)
    financials: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    notices: list[dict[str, Any]] = Field(default_factory=list)
    sector: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class GsgfFunnelDiagnostics(BaseModel):
    candidate_pool_count: int = 0
    after_static_filters_count: int = 0
    scan_limit_count: int = 0
    kline_success_count: int = 0
    kline_failure_count: int = 0
    data_incomplete_count: int = 0
    kdj_filtered_count: int = 0
    gsgf_structure_hit_count: int = 0
    confirmed_buy_count: int = 0
    low_buy_count: int = 0
    b_zone_a_point_count: int = 0
    volume_breakout_count: int = 0
    hard_risk_filtered_count: int = 0
    final_displayed_count: int = 0


class StrongStockScreeningResult(BaseModel):
    strategy: ScreenStrategy = "strong_stock"
    strong_model_version: str = "strong-v1"
    gsgf_model_version: str | None = None
    sort_version: str = "strong-sort-v1"
    trade_date: str
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    items: list[StrongStockScreeningItem] = Field(default_factory=list)
    gsgf_funnel: GsgfFunnelDiagnostics = Field(default_factory=GsgfFunnelDiagnostics)
    gsgf_observation_items: list[StrongStockScreeningItem] = Field(default_factory=list)
    watchlist_risk_items: list[StrongStockRiskItem] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class StrongStockIntradaySnapshot(BaseModel):
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    items: list[StrongStockIntradayItem] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class StrongStockDataUnavailable(RuntimeError):
    pass

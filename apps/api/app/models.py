from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ScreenStatus = Literal["focus", "wait_pullback", "reduce_risk", "data_incomplete"]
RiskAction = Literal["hold_watch", "reduce", "empty"]
IntradayAction = Literal["watch", "low_buy_watch", "reduce", "avoid_chase", "data_incomplete"]
GsgfIntradayConfirmation = Literal["盘中确认", "等待确认", "低吸确认", "减仓确认", "风险失效", "无GSGF上下文"]
SourceStatusValue = Literal["success", "failed", "disabled", "missing_key", "stale"]
CapitalFlowStatus = Literal["direct", "estimated", "unavailable"]
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
BackgroundJobStatus = Literal["pending", "running", "success", "failed", "canceled"]


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


class StockQuoteResponse(BaseModel):
    symbol: str
    name: str | None = None
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
    metrics: AuctionSnapshotMetrics = Field(default_factory=AuctionSnapshotMetrics)
    items: list[AuctionSnapshotItem] = Field(default_factory=list)
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


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

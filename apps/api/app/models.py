from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ScreenStatus = Literal["focus", "wait_pullback", "reduce_risk", "data_incomplete"]
RiskAction = Literal["hold_watch", "reduce", "empty"]
IntradayAction = Literal["watch", "low_buy_watch", "reduce", "avoid_chase", "data_incomplete"]
GsgfIntradayConfirmation = Literal["盘中确认", "等待确认", "低吸确认", "减仓确认", "风险失效", "无GSGF上下文"]
SourceStatusValue = Literal["success", "failed", "disabled", "missing_key"]
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
    model_version: str = "gsgf-v1"
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


class MarketOverviewResponse(BaseModel):
    trade_date: str | None = None
    turnover: MarketTurnoverSummary = Field(default_factory=MarketTurnoverSummary)
    advance_decline: MarketAdvanceDeclineSummary = Field(
        default_factory=MarketAdvanceDeclineSummary
    )
    sectors: list[MarketSectorStrengthItem] = Field(default_factory=list)
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


class StrongStockScreeningResult(BaseModel):
    strategy: ScreenStrategy = "strong_stock"
    strong_model_version: str = "strong-v1"
    gsgf_model_version: str | None = None
    sort_version: str = "strong-sort-v1"
    trade_date: str
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    items: list[StrongStockScreeningItem] = Field(default_factory=list)
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

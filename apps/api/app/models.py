from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ScreenStatus = Literal["focus", "wait_pullback", "reduce_risk", "data_incomplete"]
RiskAction = Literal["hold_watch", "reduce", "empty"]
IntradayAction = Literal["watch", "low_buy_watch", "reduce", "avoid_chase", "data_incomplete"]
SourceStatusValue = Literal["success", "failed", "disabled", "missing_key"]
IndustryStrength = Literal["strong", "neutral", "weak"]
RiskCheckStatus = Literal["triggered", "clear", "unknown"]


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
    signals: list[str] = Field(default_factory=list)
    source_trace: list[str] = Field(default_factory=list)


class StrongStockSourceStatus(BaseModel):
    source: str
    status: SourceStatusValue
    detail: str


class StockKlineResponse(BaseModel):
    symbol: str
    source_status: StrongStockSourceStatus
    bars: list[KlineBar] = Field(default_factory=list)


class StrongStockScreeningResult(BaseModel):
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

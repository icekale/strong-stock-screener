from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ScreenStatus = Literal["focus", "wait_pullback", "reduce_risk", "data_incomplete"]
RiskAction = Literal["hold_watch", "reduce", "empty"]
SourceStatusValue = Literal["success", "failed", "disabled", "missing_key"]


class StrongStockCandidate(BaseModel):
    symbol: str
    name: str
    limit_up_evidence: list[str] = Field(default_factory=list)
    board_note: str | None = None


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


class StrongStockScreeningItem(BaseModel):
    symbol: str
    name: str
    status: ScreenStatus
    score: int
    rule_hits: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    intraday_notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    data_status: Literal["complete", "incomplete"] = "complete"
    source_trace: list[str] = Field(default_factory=list)


class StrongStockRiskItem(BaseModel):
    symbol: str
    name: str
    risk_action: RiskAction
    risk_flags: list[str] = Field(default_factory=list)
    intraday_notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_trace: list[str] = Field(default_factory=list)


class StrongStockSourceStatus(BaseModel):
    source: str
    status: SourceStatusValue
    detail: str


class StrongStockScreeningResult(BaseModel):
    trade_date: str
    source_status: list[StrongStockSourceStatus] = Field(default_factory=list)
    items: list[StrongStockScreeningItem] = Field(default_factory=list)
    watchlist_risk_items: list[StrongStockRiskItem] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )


class StrongStockDataUnavailable(RuntimeError):
    pass


from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import (
    AuctionSnapshotItem,
    AuctionSnapshotMetrics,
    AuctionSnapshotResponse,
    MarketRankingItem,
    MarketRankingsResponse,
    StrongStockSourceStatus,
)


def build_auction_snapshot(
    rankings: MarketRankingsResponse,
    limit: int = 30,
    now: datetime | None = None,
) -> AuctionSnapshotResponse:
    bounded_limit = max(1, min(limit, 100))
    items = [_auction_item(item) for item in rankings.pct_change_rank]
    items = [item for item in items if item.open_gap_pct is not None]
    items = sorted(
        items,
        key=lambda item: (
            item.auction_score,
            item.open_gap_pct or -999,
            item.turnover_cny or 0,
            item.symbol,
        ),
        reverse=True,
    )[:bounded_limit]
    return AuctionSnapshotResponse(
        trade_date=rankings.trade_date,
        session=_auction_session(now),
        metrics=AuctionSnapshotMetrics(
            candidate_count=len(items),
            strong_high_open_count=sum(1 for item in items if (item.open_gap_pct or 0) >= 3),
            high_risk_count=sum(1 for item in items if item.risk_flags),
            total_turnover_cny=round(sum(item.turnover_cny or 0 for item in items), 2),
        ),
        items=items,
        source_status=[
            *rankings.source_status,
            StrongStockSourceStatus(
                source="竞价雷达模型",
                status="success",
                detail="基于 TickFlow 全A实时行情快照计算竞价高开、量能和风险提示",
            ),
        ],
    )


def _auction_item(item: MarketRankingItem) -> AuctionSnapshotItem:
    current_pct_change = item.current_pct_change if item.current_pct_change is not None else item.pct_change
    open_gap_pct = _open_gap_pct(item.open_price, item.prev_close)
    if open_gap_pct is None:
        open_gap_pct = current_pct_change
    turnover_cny = item.turnover_cny
    turnover_rate = item.turnover_rate
    signals: list[str] = []
    risk_flags: list[str] = []
    tier = "neutral"
    action_note = "竞价信号不突出，等待盘中趋势确认。"

    if open_gap_pct is not None:
        if open_gap_pct >= 7:
            signals.append("竞价强势高开")
            risk_flags.append("高开需防冲高回落")
        elif open_gap_pct >= 3:
            signals.append("竞价温和高开")
        elif open_gap_pct <= -3:
            risk_flags.append("竞价低开偏弱")

    if open_gap_pct is not None and current_pct_change is not None:
        if open_gap_pct <= -3 and current_pct_change >= 3:
            signals.append("低开转强观察")
        elif open_gap_pct <= -3 and current_pct_change <= -3:
            risk_flags.append("低开后延续走弱")

    if turnover_cny is not None:
        if turnover_cny >= 1_000_000_000:
            signals.append("竞价成交额居前")
        elif turnover_cny >= 300_000_000:
            signals.append("竞价量能活跃")

    if turnover_rate is not None:
        if turnover_rate >= 10:
            signals.append("换手充分")
        elif turnover_rate >= 5:
            signals.append("换手放大")

    tier, action_note = _auction_tier(open_gap_pct, current_pct_change, turnover_cny, turnover_rate, risk_flags, signals)
    score = _auction_score(open_gap_pct, turnover_cny, turnover_rate)
    return AuctionSnapshotItem(
        symbol=item.symbol,
        name=item.name,
        industry=item.industry,
        last_price=item.last_price,
        current_pct_change=current_pct_change,
        open_gap_pct=open_gap_pct,
        turnover_rate=turnover_rate,
        turnover_cny=turnover_cny,
        volume=item.volume,
        auction_score=score,
        tier=tier,
        action_note=action_note,
        signals=signals,
        risk_flags=risk_flags,
        quote_time=item.quote_time,
    )


def _auction_score(
    open_gap_pct: float | None,
    turnover_cny: float | None,
    turnover_rate: float | None,
) -> float:
    gap_score = min(max(open_gap_pct or 0, -5), 10) * 8
    amount_score = min((turnover_cny or 0) / 100_000_000, 30)
    turnover_score = min((turnover_rate or 0) * 1.5, 25)
    return round(gap_score + amount_score + turnover_score, 2)


def _open_gap_pct(open_price: float | None, prev_close: float | None) -> float | None:
    if open_price is None or prev_close is None or prev_close <= 0:
        return None
    return round((open_price - prev_close) / prev_close * 100, 4)


def _auction_tier(
    open_gap_pct: float | None,
    current_pct_change: float | None,
    turnover_cny: float | None,
    turnover_rate: float | None,
    risk_flags: list[str],
    signals: list[str],
) -> tuple[str, str]:
    if open_gap_pct is not None and open_gap_pct >= 7:
        return "risk_overheat", "高开过热，只适合观察封单与承接，不追高。"
    if open_gap_pct is not None and open_gap_pct <= -3 and current_pct_change is not None and current_pct_change >= 3:
        return "reversal_watch", "低开后快速转强，适合观察是否站稳分时均线。"
    if open_gap_pct is not None and open_gap_pct <= -3:
        return "weak_low_open", "低开偏弱，先看修复力度，不急于低吸。"
    if (turnover_cny or 0) >= 300_000_000 or (turnover_rate or 0) >= 5:
        return "volume_leader", "量能活跃，结合板块强度和开盘承接继续筛选。"
    if open_gap_pct is not None and open_gap_pct >= 3:
        return "strong_high_open", "温和高开，优先观察开盘后是否放量延续。"
    if risk_flags:
        return "weak_low_open", "风险信号优先，等待盘中修复确认。"
    if signals:
        return "volume_leader", "有竞价信号，但需要盘中成交继续确认。"
    return "neutral", "竞价信号不突出，等待盘中趋势确认。"


def _auction_session(now: datetime | None = None) -> str:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    hhmm = current.hour * 100 + current.minute
    if 915 <= hhmm < 925:
        return "call_auction"
    if 925 <= hhmm < 930:
        return "pre_open"
    if 930 <= hhmm <= 1505:
        return "continuous"
    return "closed"

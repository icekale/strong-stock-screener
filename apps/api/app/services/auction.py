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

HotThemeRef = tuple[str, int, float]


def build_auction_snapshot(
    rankings: MarketRankingsResponse,
    limit: int = 30,
    now: datetime | None = None,
    hot_themes: list[HotThemeRef] | None = None,
) -> AuctionSnapshotResponse:
    bounded_limit = max(1, min(limit, 100))
    hot_theme_refs = _normalize_hot_theme_refs(hot_themes or [])
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
    items = _enrich_hot_theme_links(items, hot_theme_refs)
    source_status = [
        *rankings.source_status,
        StrongStockSourceStatus(
            source="竞价雷达模型",
            status="success",
            detail="基于 TickFlow 全A实时行情快照计算竞价高开、量能和风险提示；09:25 后主榜锁定",
        ),
    ]
    if hot_theme_refs:
        linked_count = sum(1 for item in items if item.hot_theme_rank is not None)
        source_status.append(
            StrongStockSourceStatus(
                source="短线题材联动",
                status="success",
                detail=f"参考短线题材 Top{len(hot_theme_refs)}，匹配 {linked_count} 只竞价候选",
            )
        )
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
        source_status=source_status,
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


def _normalize_hot_theme_refs(hot_themes: list[HotThemeRef]) -> list[HotThemeRef]:
    output: list[HotThemeRef] = []
    seen: set[str] = set()
    for name, rank, score in hot_themes:
        clean_name = str(name).strip()
        if not clean_name or clean_name in seen:
            continue
        seen.add(clean_name)
        output.append((clean_name, int(rank), float(score)))
    return sorted(output, key=lambda item: item[1])[:10]


def _enrich_hot_theme_links(
    items: list[AuctionSnapshotItem],
    hot_theme_refs: list[HotThemeRef],
) -> list[AuctionSnapshotItem]:
    if not hot_theme_refs:
        return items

    matched_theme_by_symbol: dict[str, HotThemeRef] = {}
    for item in items:
        match = _best_hot_theme_match(item, hot_theme_refs)
        if match is not None:
            matched_theme_by_symbol[item.symbol] = match

    theme_members: dict[str, list[AuctionSnapshotItem]] = {}
    for item in items:
        match = matched_theme_by_symbol.get(item.symbol)
        if match is None:
            continue
        theme_members.setdefault(match[0], []).append(item)
    theme_rank_by_symbol: dict[str, int] = {}
    for members in theme_members.values():
        ranked = sorted(
            members,
            key=lambda item: (item.auction_score, item.open_gap_pct or -999, item.turnover_cny or 0, item.symbol),
            reverse=True,
        )
        for index, item in enumerate(ranked, start=1):
            theme_rank_by_symbol[item.symbol] = index

    output: list[AuctionSnapshotItem] = []
    for item in items:
        match = matched_theme_by_symbol.get(item.symbol)
        if match is None:
            output.append(item)
            continue
        theme_name, theme_rank, theme_score = match
        theme_auction_rank = theme_rank_by_symbol.get(item.symbol)
        resonance = theme_rank <= 10 and theme_auction_rank is not None and theme_auction_rank <= 3
        signals = list(item.signals)
        if resonance and "题材共振" not in signals:
            signals.append("题材共振")
        output.append(
            item.model_copy(
                update={
                    "themes": [theme_name],
                    "hot_theme_rank": theme_rank,
                    "hot_theme_score": theme_score,
                    "theme_auction_rank": theme_auction_rank,
                    "theme_resonance": resonance,
                    "signals": signals,
                }
            )
        )
    return output


def _best_hot_theme_match(item: AuctionSnapshotItem, hot_theme_refs: list[HotThemeRef]) -> HotThemeRef | None:
    industry = _normalize_theme_text(item.industry or "")
    if not industry:
        return None
    for theme in hot_theme_refs:
        theme_text = _normalize_theme_text(theme[0])
        if not theme_text:
            continue
        if industry in theme_text or theme_text in industry:
            return theme
    return None


def _normalize_theme_text(value: str) -> str:
    return (
        value.replace("概念", "")
        .replace("板块", "")
        .replace("行业", "")
        .replace("指数", "")
        .replace(" ", "")
        .strip()
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
    if open_price is None or open_price <= 0 or prev_close is None or prev_close <= 0:
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

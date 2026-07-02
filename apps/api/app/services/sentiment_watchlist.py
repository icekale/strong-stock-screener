from __future__ import annotations

from app.models import SentimentDecisionResponse, SentimentWatchlistAlert
from app.providers.watchlist import WatchlistItem


def build_sentiment_watchlist_alerts(
    decision: SentimentDecisionResponse,
    watchlist_items: list[WatchlistItem],
) -> list[SentimentWatchlistAlert]:
    main_sector_names = {item.name for item in decision.main_sectors}
    main_symbols = {symbol for sector in decision.main_sectors for symbol in sector.symbols}
    output: list[SentimentWatchlistAlert] = []
    for item in watchlist_items:
        reasons: list[str] = []
        matched_sector = None
        if item.group in main_sector_names:
            matched_sector = item.group
            reasons.append("命中主线板块")
        if item.symbol in main_symbols:
            reasons.append("属于主线代表股票")
        if decision.trade_permission in {"空仓等待", "只卖不追"} or decision.risk_level == "高":
            action = "风险回避"
            reasons.append(f"当前交易许可为{decision.trade_permission}")
        elif reasons:
            action = "重点盯"
        else:
            action = "等确认"
        output.append(
            SentimentWatchlistAlert(
                symbol=item.symbol,
                name=item.name or item.symbol,
                group=item.group,
                tags=item.tags,
                action=action,
                matched_sector=matched_sector,
                reasons=reasons or ["未命中当前主线，等待确认"],
            )
        )
    return sorted(output, key=_sort_key)


def _sort_key(item: SentimentWatchlistAlert) -> tuple[int, str]:
    rank = {"重点盯": 0, "等确认": 1, "风险回避": 2}
    return (rank[item.action], item.symbol)

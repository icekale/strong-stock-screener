from __future__ import annotations

from datetime import datetime
from statistics import mean

from app.models import AuctionReviewRecord, AuctionReviewSnapshot, AuctionSnapshotItem, AuctionSnapshotResponse


def build_auction_review_records(
    snapshot: AuctionSnapshotResponse,
    *,
    selected_at_label: str,
    selected_at: datetime,
    limit: int = 100,
) -> list[AuctionReviewRecord]:
    trade_date = snapshot.trade_date or selected_at.date().isoformat()
    items = snapshot.items[: max(1, limit)]
    concentrated_industries = _concentrated_industries(items)
    records: list[AuctionReviewRecord] = []
    for index, item in enumerate(items, start=1):
        records.append(
            AuctionReviewRecord(
                trade_date=trade_date,
                symbol=item.symbol,
                name=item.name,
                industry=item.industry,
                selected_at_label=selected_at_label,
                selected_at=selected_at.isoformat(timespec="seconds"),
                auction_snapshot=AuctionReviewSnapshot(
                    open_gap_pct=item.open_gap_pct,
                    current_pct_change=item.current_pct_change,
                    turnover_rate=item.turnover_rate,
                    turnover_cny=item.turnover_cny,
                    volume=item.volume,
                    auction_score=item.auction_score,
                    rank=index,
                    tier=item.tier,
                    signals=item.signals,
                    risk_flags=item.risk_flags,
                    quote_time=item.quote_time,
                ),
                rule_tags=_rule_tags(item, item.industry in concentrated_industries),
                source_status=snapshot.source_status,
            )
        )
    return records


def _rule_tags(item: AuctionSnapshotItem, industry_concentrated: bool) -> list[str]:
    tags: list[str] = []
    open_gap_pct = item.open_gap_pct
    current_pct_change = item.current_pct_change
    turnover_cny = item.turnover_cny or 0
    turnover_rate = item.turnover_rate or 0
    if open_gap_pct is not None:
        if open_gap_pct >= 7:
            tags.append("强势高开")
        elif open_gap_pct >= 3:
            tags.append("温和高开")
        elif open_gap_pct <= -3 and current_pct_change is not None and current_pct_change >= 3:
            tags.append("低开转强")
        elif open_gap_pct <= -3 and current_pct_change is not None and current_pct_change <= -3:
            tags.append("低开偏弱")
    if turnover_cny >= 1_000_000_000:
        tags.append("成交额居前")
    if turnover_cny >= 300_000_000 or turnover_rate >= 5:
        tags.append("量能活跃")
    if any("高开" in flag and "回落" in flag for flag in item.risk_flags) or item.tier == "risk_overheat":
        tags.append("高开过热")
    if industry_concentrated:
        tags.append("行业集中")
    return list(dict.fromkeys(tags))


def _concentrated_industries(items: list[AuctionSnapshotItem]) -> set[str]:
    industries = [item.industry for item in items if item.industry]
    if len(industries) < 2:
        return set()
    threshold = max(2, round(len(items) * 0.4))
    return {
        industry
        for industry in set(industries)
        if sum(1 for value in industries if value == industry) >= threshold
        and sum(1 for value in industries if value == industry) >= mean([1, len(industries) / 5])
    }

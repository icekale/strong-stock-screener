from __future__ import annotations

from datetime import datetime
from statistics import mean

from app.models import (
    AuctionReviewOutcome,
    AuctionReviewRecord,
    AuctionReviewScore,
    AuctionReviewSnapshot,
    AuctionReviewSummary,
    AuctionRuleBucket,
    AuctionSnapshotItem,
    AuctionSnapshotResponse,
    KlineBar,
)


def build_auction_review_records(
    snapshot: AuctionSnapshotResponse,
    *,
    selected_at_label: str,
    selected_at: datetime,
    limit: int = 100,
) -> list[AuctionReviewRecord]:
    trade_date = selected_at.date().isoformat()
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


def finalize_auction_records(
    records: list[AuctionReviewRecord],
    *,
    symbol_bars: dict[str, list[KlineBar]],
    symbol_intraday_bars: dict[str, list[KlineBar]] | None = None,
) -> AuctionReviewSummary:
    reviewed = [
        _finalize_record(
            record,
            sorted(symbol_bars.get(record.symbol, []), key=lambda bar: bar.date),
            sorted((symbol_intraday_bars or {}).get(record.symbol, []), key=lambda bar: bar.date),
        )
        for record in records
    ]
    return AuctionReviewSummary(
        trade_date=records[0].trade_date if records else None,
        record_count=len(reviewed),
        pending_count=sum(1 for record in reviewed if record.review_status == "pending"),
        completed_count=sum(1 for record in reviewed if record.review_status == "next_day_done"),
        data_incomplete_count=sum(1 for record in reviewed if record.review_status == "data_incomplete"),
        records=reviewed,
        buckets=build_auction_rule_buckets(reviewed),
    )


def build_auction_rule_buckets(records: list[AuctionReviewRecord]) -> list[AuctionRuleBucket]:
    grouped: dict[str, list[AuctionReviewRecord]] = {}
    for record in records:
        for tag in record.rule_tags:
            grouped.setdefault(tag, []).append(record)
    buckets: list[AuctionRuleBucket] = []
    for tag, group in grouped.items():
        scores = [record.score.total_score for record in group if record.score.total_score is not None]
        intraday_peaks = [
            record.intraday_result.peak_pct for record in group if record.intraday_result.peak_pct is not None
        ]
        closes = [record.day_result.close_pct for record in group if record.day_result.close_pct is not None]
        next_opens = [
            record.next_day_result.open_pct for record in group if record.next_day_result.open_pct is not None
        ]
        drawdowns = [record.day_result.drawdown_pct for record in group if record.day_result.drawdown_pct is not None]
        wins = sum(1 for record in group if (record.score.total_score or 0) >= 50)
        failures = len(group) - wins
        sample_count = len(group)
        win_rate = round(wins / sample_count, 4) if sample_count else None
        avg_score = _avg(scores)
        buckets.append(
            AuctionRuleBucket(
                rule_tag=tag,
                sample_count=sample_count,
                win_rate=win_rate,
                avg_score=avg_score,
                avg_intraday_peak_pct=_avg(intraday_peaks),
                avg_close_pct=_avg(closes),
                avg_next_open_pct=_avg(next_opens),
                avg_drawdown_pct=_avg(drawdowns),
                failure_count=failures,
                suggestion=_bucket_suggestion(sample_count, win_rate, avg_score, _avg(drawdowns)),
            )
        )
    return sorted(buckets, key=lambda bucket: (bucket.avg_score or -999, bucket.sample_count), reverse=True)


def score_auction_record(record: AuctionReviewRecord) -> AuctionReviewScore:
    intraday_score = _score_window(
        record.intraday_result.peak_pct,
        record.intraday_result.close_pct,
        record.intraday_result.drawdown_pct,
    )
    day_score = _score_window(record.day_result.peak_pct, record.day_result.close_pct, record.day_result.drawdown_pct)
    next_day_score = _score_window(
        record.next_day_result.peak_pct,
        record.next_day_result.close_pct,
        record.day_result.drawdown_pct,
    )
    available = [score for score in [intraday_score, day_score, next_day_score] if score is not None]
    return AuctionReviewScore(
        intraday_score=intraday_score,
        day_score=day_score,
        next_day_score=next_day_score,
        total_score=round(mean(available), 2) if available else None,
    )


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


def _finalize_record(
    record: AuctionReviewRecord,
    bars: list[KlineBar],
    intraday_bars: list[KlineBar],
) -> AuctionReviewRecord:
    signal_index = _signal_index(record.trade_date, bars)
    if signal_index is None:
        return record.model_copy(update={"review_status": "pending"})
    previous_close = bars[signal_index - 1].close if signal_index > 0 else bars[signal_index].open
    day_bar = bars[signal_index]
    next_day_bar = bars[signal_index + 1] if signal_index + 1 < len(bars) else None
    intraday_result = _intraday_outcome(record.trade_date, previous_close, intraday_bars)
    day_result = _day_outcome(previous_close, day_bar)
    next_day_result = _next_day_outcome(day_bar.close, next_day_bar)
    status = _review_status(intraday_result, day_result, next_day_result)
    updated = record.model_copy(
        deep=True,
        update={
            "intraday_result": intraday_result,
            "day_result": day_result,
            "next_day_result": next_day_result,
            "review_status": status,
        },
    )
    return updated.model_copy(update={"score": score_auction_record(updated)})


def _intraday_outcome(trade_date: str, base_price: float, bars: list[KlineBar]) -> AuctionReviewOutcome:
    scoped = [bar for bar in bars if bar.date.startswith(trade_date) and _bar_seconds(bar) <= 10 * 3600]
    if not scoped or base_price <= 0:
        return AuctionReviewOutcome(status="data_incomplete")
    return AuctionReviewOutcome(
        peak_pct=_pct(max(bar.high for bar in scoped), base_price),
        close_pct=_pct(scoped[-1].close, base_price),
        drawdown_pct=min(_pct(min(bar.low for bar in scoped), base_price), 0),
        status="complete",
    )


def _day_outcome(base_price: float, bar: KlineBar) -> AuctionReviewOutcome:
    if base_price <= 0:
        return AuctionReviewOutcome(status="data_incomplete")
    return AuctionReviewOutcome(
        peak_pct=_pct(bar.high, base_price),
        close_pct=_pct(bar.close, base_price),
        drawdown_pct=min(_pct(bar.low, base_price), 0),
        limit_up=_pct(bar.close, base_price) >= 9.8,
        status="complete",
    )


def _next_day_outcome(base_price: float, bar: KlineBar | None) -> AuctionReviewOutcome:
    if bar is None or base_price <= 0:
        return AuctionReviewOutcome(status="pending")
    close_pct = _pct(bar.close, base_price)
    return AuctionReviewOutcome(
        open_pct=_pct(bar.open, base_price),
        peak_pct=_pct(bar.high, base_price),
        close_pct=close_pct,
        drawdown_pct=min(_pct(bar.low, base_price), 0),
        strong_follow=close_pct >= 3,
        status="complete",
    )


def _review_status(
    intraday_result: AuctionReviewOutcome,
    day_result: AuctionReviewOutcome,
    next_day_result: AuctionReviewOutcome,
) -> str:
    if intraday_result.status == "data_incomplete":
        return "data_incomplete"
    if next_day_result.status == "complete":
        return "next_day_done"
    if day_result.status == "complete":
        return "day_done"
    return "pending"


def _score_window(
    peak_pct: float | None,
    close_pct: float | None,
    drawdown_pct: float | None,
) -> float | None:
    if peak_pct is None and close_pct is None:
        return None
    peak_score = min(max((peak_pct or 0) * 4, -20), 45)
    close_score = min(max((close_pct or 0) * 4, -30), 45)
    drawdown_penalty = min(abs(drawdown_pct or 0) * 2, 25)
    return round(max(0, min(100, 20 + peak_score + close_score - drawdown_penalty)), 2)


def _bucket_suggestion(
    sample_count: int,
    win_rate: float | None,
    avg_score: float | None,
    avg_drawdown: float | None,
) -> str:
    if sample_count < 2:
        return "样本不足，不建议调整。"
    if (avg_drawdown or 0) <= -8:
        return "平均回撤偏大，建议标记风险或降低仓位权重。"
    if (win_rate or 0) >= 0.6 and (avg_score or 0) >= 55:
        return "历史表现较好，可提高观察优先级。"
    if (win_rate or 0) < 0.55:
        return "胜率偏低，建议增加过滤条件或降低权重。"
    return "表现中性，继续积累样本。"


def _signal_index(trade_date: str, bars: list[KlineBar]) -> int | None:
    for index, bar in enumerate(bars):
        if bar.date == trade_date:
            return index
    return None


def _bar_seconds(bar: KlineBar) -> int:
    parts = bar.date.split()
    if len(parts) < 2:
        return 24 * 3600
    hour_text, minute_text = parts[1].split(":")[:2]
    return int(hour_text) * 3600 + int(minute_text) * 60


def _pct(value: float, base: float) -> float:
    return round((value / base - 1) * 100, 2)


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(mean(clean), 2) if clean else None


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

from __future__ import annotations

import re
from collections import defaultdict
from typing import Protocol

from app.models import (
    IntradayAction,
    MarketEmotionBucket,
    MarketEmotionMetrics,
    MarketEmotionSnapshotResponse,
    SentimentSnapshotStatus,
    SentimentSummaryMetrics,
    SentimentSummaryResponse,
    MarketOverviewResponse,
    ShortTermAlertSeverity,
    ShortTermIntradaySentimentItem,
    ShortTermIntradaySentimentMetrics,
    ShortTermIntradaySentimentResponse,
    ShortTermIntradaySignalAlert,
    ShortTermIntradaySignalDigest,
    ShortTermSentimentIndustryItem,
    ShortTermSentimentLadderGroup,
    ShortTermSentimentMetrics,
    ShortTermSentimentResponse,
    ShortTermSentimentStockItem,
    StrongStockCandidate,
    StrongStockDataUnavailable,
    StrongStockSourceStatus,
)
from app.providers.tickflow import TickFlowIntradayBar, TickFlowQuote
from app.services.intraday import IntradayMonitor


class CandidateProvider(Protocol):
    source_name: str

    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        ...


class IntradayQuoteProvider(Protocol):
    source_name: str

    def get_quotes(self, symbols: list[str]) -> list[TickFlowQuote]:
        ...

    def get_intraday_bars(
        self,
        symbols: list[str],
        period: str = "1m",
        count: int = 120,
    ) -> dict[str, list[TickFlowIntradayBar]]:
        ...


class MarketOverviewProvider(Protocol):
    def get_overview(self) -> MarketOverviewResponse:
        ...


class MarketDistributionProvider(MarketOverviewProvider, Protocol):
    def get_pct_change_distribution(self) -> tuple[list[MarketEmotionBucket], StrongStockSourceStatus]:
        ...


def build_short_term_sentiment(
    candidate_provider: CandidateProvider,
    trade_date: str,
    limit: int = 50,
) -> ShortTermSentimentResponse:
    try:
        candidates = candidate_provider.get_candidates(trade_date)
    except StrongStockDataUnavailable:
        raise
    except Exception as exc:
        raise StrongStockDataUnavailable(f"短线情绪候选池获取失败: {exc.__class__.__name__}") from exc

    items = [_stock_item(candidate) for candidate in candidates]
    trade_date_key = _date_key(trade_date)
    limit_up_pool = [
        item
        for item in items
        if item.last_limit_up_date is not None and _date_key(item.last_limit_up_date) == trade_date_key
    ]
    break_board_pool = [item for item in items if item.break_board_count > 0]

    limit_up_pool = sorted(limit_up_pool, key=_stock_sort_key)[:limit]
    break_board_pool = sorted(break_board_pool, key=_break_sort_key)[:limit]
    ladder = _build_ladder(limit_up_pool)
    hot_industries = _build_hot_industries(limit_up_pool, break_board_pool)
    metrics = ShortTermSentimentMetrics(
        limit_up_count=len(limit_up_pool),
        break_board_count=len(break_board_pool),
        max_consecutive_boards=max((item.board_count for item in limit_up_pool), default=0),
        hot_industry_count=len(hot_industries),
    )

    return ShortTermSentimentResponse(
        trade_date=trade_date,
        metrics=metrics,
        limit_up_pool=limit_up_pool,
        break_board_pool=break_board_pool,
        ladder=ladder,
        hot_industries=hot_industries,
        source_status=[
            StrongStockSourceStatus(
                source=getattr(candidate_provider, "source_name", "涨停候选池"),
                status="success",
                detail=f"基于近20日涨停候选池派生，候选 {len(candidates)} 只",
            )
        ],
    )


def build_market_emotion_snapshot(
    candidate_provider: CandidateProvider,
    market_overview_provider: MarketOverviewProvider,
    trade_date: str,
    limit: int = 80,
    sentiment_snapshot: ShortTermSentimentResponse | None = None,
) -> MarketEmotionSnapshotResponse:
    sentiment = sentiment_snapshot or build_short_term_sentiment(
        candidate_provider,
        trade_date=trade_date,
        limit=limit,
    )
    try:
        overview = market_overview_provider.get_overview()
    except StrongStockDataUnavailable:
        raise
    except Exception as exc:
        raise StrongStockDataUnavailable(f"全市场情绪概览获取失败: {exc.__class__.__name__}") from exc

    advance_decline = overview.advance_decline
    turnover = overview.turnover
    seal_rate = _seal_rate(
        sentiment.metrics.limit_up_count,
        sentiment.metrics.break_board_count,
    )
    losing_effect = _losing_effect_score(
        advance_count=advance_decline.advance_count,
        decline_count=advance_decline.decline_count,
        break_board_count=sentiment.metrics.break_board_count,
        limit_down_count=advance_decline.limit_down_count,
    )
    emotion_score = _market_emotion_score(
        advance_count=advance_decline.advance_count,
        decline_count=advance_decline.decline_count,
        limit_up_count=sentiment.metrics.limit_up_count,
        break_board_count=sentiment.metrics.break_board_count,
        max_boards=sentiment.metrics.max_consecutive_boards,
        seal_rate_pct=seal_rate,
        turnover_change_pct=turnover.change_pct,
    )
    buckets, distribution_status = _market_distribution(market_overview_provider)
    source_status = [
        *sentiment.source_status,
        *overview.source_status,
        distribution_status,
        StrongStockSourceStatus(
            source="市场情绪模型",
            status="success",
            detail="基于涨停池、炸板池、全A涨跌家数、成交额变化计算实时情绪快照",
        ),
        StrongStockSourceStatus(
            source="日内情绪曲线",
            status="disabled",
            detail="待后台采样任务流启用后生成真实分时曲线",
        ),
    ]

    return MarketEmotionSnapshotResponse(
        trade_date=trade_date,
        metrics=MarketEmotionMetrics(
            emotion_score=emotion_score,
            emotion_level=_emotion_level(emotion_score),
            limit_up_count=sentiment.metrics.limit_up_count,
            break_board_count=sentiment.metrics.break_board_count,
            limit_down_count=advance_decline.limit_down_count,
            losing_effect_score=losing_effect,
            max_consecutive_boards=sentiment.metrics.max_consecutive_boards,
            advance_count=advance_decline.advance_count,
            decline_count=advance_decline.decline_count,
            seal_rate_pct=seal_rate,
            turnover_cny=turnover.total_cny,
            turnover_change_cny=turnover.change_cny,
            turnover_change_pct=turnover.change_pct,
            main_flow_cny=None,
            yesterday_limit_up_performance_pct=None,
            yesterday_ladder_performance_pct=None,
        ),
        buckets=buckets,
        source_status=source_status,
        notes=[
            "第一版为盘中实时快照：涨停/炸板来自候选池，全A涨跌家数与成交额来自市场概览源。",
            "涨跌幅分布优先使用实时全市场个股行情；数据源失败时保留空桶并标注状态。",
            "分时曲线需要后台定时采样沉淀；当前仅返回当前情绪落点。",
        ],
    )


def build_sentiment_summary(
    sentiment: ShortTermSentimentResponse,
    market_emotion: MarketEmotionSnapshotResponse,
    snapshot_status: SentimentSnapshotStatus = "fresh",
    cached_at: str | None = None,
) -> SentimentSummaryResponse:
    metrics = market_emotion.metrics
    return SentimentSummaryResponse(
        trade_date=sentiment.trade_date,
        snapshot_status=snapshot_status,
        cached_at=cached_at,
        metrics=SentimentSummaryMetrics(
            emotion_score=metrics.emotion_score,
            emotion_level=metrics.emotion_level,
            limit_up_count=sentiment.metrics.limit_up_count,
            break_board_count=sentiment.metrics.break_board_count,
            limit_down_count=metrics.limit_down_count,
            losing_effect_score=metrics.losing_effect_score,
            max_consecutive_boards=sentiment.metrics.max_consecutive_boards,
            advance_count=metrics.advance_count,
            decline_count=metrics.decline_count,
            seal_rate_pct=metrics.seal_rate_pct,
            turnover_cny=metrics.turnover_cny,
            turnover_change_cny=metrics.turnover_change_cny,
            turnover_change_pct=metrics.turnover_change_pct,
        ),
        hot_industries=sentiment.hot_industries[:10],
        source_status=_dedupe_source_status([*sentiment.source_status, *market_emotion.source_status]),
        notes=market_emotion.notes,
    )


def build_missing_sentiment_summary(trade_date: str) -> SentimentSummaryResponse:
    return SentimentSummaryResponse(
        trade_date=trade_date,
        snapshot_status="missing",
        source_status=[
            StrongStockSourceStatus(
                source="短线情绪快照",
                status="stale",
                detail="暂无本交易日快照，请手动刷新生成",
            )
        ],
        notes=["暂无本交易日缓存快照。点击刷新情绪后会调用真实数据源生成。"],
    )


def _dedupe_source_status(items: list[StrongStockSourceStatus]) -> list[StrongStockSourceStatus]:
    output: list[StrongStockSourceStatus] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.source, item.status, item.detail)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def build_short_term_intraday_sentiment(
    candidate_provider: CandidateProvider,
    quote_provider: IntradayQuoteProvider,
    trade_date: str,
    limit: int = 80,
    period: str = "1m",
    count: int = 120,
) -> ShortTermIntradaySentimentResponse:
    sentiment = build_short_term_sentiment(
        candidate_provider,
        trade_date=trade_date,
        limit=limit,
    )
    symbols = _intraday_symbols(sentiment)
    if not symbols:
        raise StrongStockDataUnavailable("短线情绪盘中监控标的为空")

    stock_map = {
        item.symbol: item
        for item in [*sentiment.limit_up_pool, *sentiment.break_board_pool]
    }
    monitor = IntradayMonitor(quote_provider=quote_provider)
    snapshot = monitor.snapshot(
        symbols=symbols,
        name_map={symbol: stock_map[symbol].name for symbol in symbols if symbol in stock_map},
        industry_map={
            symbol: stock_map[symbol].industry
            for symbol in symbols
            if symbol in stock_map and stock_map[symbol].industry
        },
        limit=limit,
        period=period,
        count=count,
    )
    items = [
        ShortTermIntradaySentimentItem(
            symbol=item.symbol,
            name=item.name,
            industry=item.industry,
            pool_tags=_pool_tags(stock_map.get(item.symbol), sentiment),
            action=item.action,
            last_price=item.last_price,
            pct_change=item.pct_change,
            open_gap_pct=item.open_gap_pct,
            intraday_ma=item.intraday_ma,
            latest_vs_intraday_ma_pct=item.latest_vs_intraday_ma_pct,
            turnover_cny=item.turnover_cny,
            signals=item.signals,
        )
        for item in snapshot.items
    ]
    items.sort(key=_intraday_sort_key)
    return ShortTermIntradaySentimentResponse(
        trade_date=trade_date,
        metrics=ShortTermIntradaySentimentMetrics(
            watched_count=len(items),
            alert_count=sum(1 for item in items if _is_alert_action(item.action)),
            reduce_count=sum(1 for item in items if item.action == "reduce"),
            low_buy_watch_count=sum(1 for item in items if item.action == "low_buy_watch"),
            avoid_chase_count=sum(1 for item in items if item.action == "avoid_chase"),
        ),
        items=items,
        source_status=snapshot.source_status,
    )


def build_short_term_intraday_signal_digest(
    snapshot: ShortTermIntradaySentimentResponse,
    max_alerts: int = 8,
) -> ShortTermIntradaySignalDigest:
    alerts = [
        _signal_alert(item)
        for item in snapshot.items
        if _is_alert_action(item.action)
    ]
    alerts.sort(key=_alert_sort_key)
    alerts = alerts[:max_alerts]
    title = f"短线情绪提醒 · {snapshot.trade_date}"
    return ShortTermIntradaySignalDigest(
        title=title,
        trade_date=snapshot.trade_date,
        alert_count=len(alerts),
        alerts=alerts,
        message_text=_digest_message(title, alerts, snapshot),
        source_status=snapshot.source_status,
    )


def _stock_item(candidate: StrongStockCandidate) -> ShortTermSentimentStockItem:
    note = candidate.board_note or ""
    return ShortTermSentimentStockItem(
        symbol=candidate.symbol,
        name=candidate.name,
        industry=candidate.industry,
        board_count=max(1, _int_field(note, "连板数") or 1),
        limit_up_hits_20d=_limit_up_hits(candidate),
        break_board_count=max(0, _int_field(note, "炸板次数") or 0),
        last_limit_up_date=_last_limit_up_date(candidate),
        first_seal_time=_text_field(note, "首次封板时间"),
        last_seal_time=_text_field(note, "最后封板时间"),
        board_note=candidate.board_note,
        limit_up_evidence=candidate.limit_up_evidence,
    )


def _build_ladder(items: list[ShortTermSentimentStockItem]) -> list[ShortTermSentimentLadderGroup]:
    grouped: dict[int, list[ShortTermSentimentStockItem]] = defaultdict(list)
    for item in items:
        grouped[item.board_count].append(item)
    return [
        ShortTermSentimentLadderGroup(
            board_count=board_count,
            label=f"{board_count}连板" if board_count > 1 else "首板",
            items=sorted(grouped[board_count], key=_stock_sort_key),
        )
        for board_count in sorted(grouped, reverse=True)
    ]


def _build_hot_industries(
    limit_up_pool: list[ShortTermSentimentStockItem],
    break_board_pool: list[ShortTermSentimentStockItem],
) -> list[ShortTermSentimentIndustryItem]:
    industry_items: dict[str, list[ShortTermSentimentStockItem]] = defaultdict(list)
    for item in limit_up_pool:
        industry_items[item.industry or "未分行业"].append(item)

    break_counts: dict[str, int] = defaultdict(int)
    for item in break_board_pool:
        break_counts[item.industry or "未分行业"] += item.break_board_count

    output: list[ShortTermSentimentIndustryItem] = []
    for industry, items in industry_items.items():
        leader = max(items, key=lambda item: (item.board_count, item.limit_up_hits_20d, item.symbol))
        limit_up_count = len(items)
        max_boards = max(item.board_count for item in items)
        break_board_count = break_counts[industry]
        strength_score = limit_up_count * 10 + max_boards * 4 - min(break_board_count * 2, 8)
        output.append(
            ShortTermSentimentIndustryItem(
                name=industry,
                limit_up_count=limit_up_count,
                break_board_count=break_board_count,
                max_consecutive_boards=max_boards,
                leader=leader.name,
                symbols=[item.symbol for item in sorted(items, key=_stock_sort_key)],
                strength_score=round(strength_score, 2),
            )
        )
    return sorted(
        output,
        key=lambda item: (item.strength_score, item.limit_up_count, item.max_consecutive_boards, item.name),
        reverse=True,
    )


def _intraday_symbols(sentiment: ShortTermSentimentResponse) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in [*sentiment.limit_up_pool, *sentiment.break_board_pool]:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        output.append(item.symbol)
    return output


def _pool_tags(
    item: ShortTermSentimentStockItem | None,
    sentiment: ShortTermSentimentResponse,
) -> list[str]:
    if item is None:
        return []
    limit_up_symbols = {stock.symbol for stock in sentiment.limit_up_pool}
    break_board_symbols = {stock.symbol for stock in sentiment.break_board_pool}
    tags: list[str] = []
    if item.symbol in limit_up_symbols:
        tags.append("涨停池")
    if item.symbol in break_board_symbols:
        tags.append("炸板池")
    tags.append(f"{item.board_count}连板" if item.board_count > 1 else "首板")
    if item.industry:
        tags.append(item.industry)
    return tags


def _intraday_sort_key(item: ShortTermIntradaySentimentItem) -> tuple[int, float, str]:
    priority: dict[IntradayAction, int] = {
        "avoid_chase": 0,
        "reduce": 1,
        "low_buy_watch": 2,
        "watch": 3,
        "data_incomplete": 4,
    }
    return (priority[item.action], -(item.pct_change or -100), item.symbol)


def _is_alert_action(action: IntradayAction) -> bool:
    return action in {"reduce", "low_buy_watch", "avoid_chase"}


def _signal_alert(item: ShortTermIntradaySentimentItem) -> ShortTermIntradaySignalAlert:
    return ShortTermIntradaySignalAlert(
        symbol=item.symbol,
        name=item.name,
        industry=item.industry,
        action=item.action,
        severity=_alert_severity(item),
        pool_tags=item.pool_tags,
        pct_change=item.pct_change,
        turnover_cny=item.turnover_cny,
        reasons=_alert_reasons(item),
    )


def _alert_severity(item: ShortTermIntradaySentimentItem) -> ShortTermAlertSeverity:
    if item.action in {"reduce", "avoid_chase"}:
        return "high"
    if item.action == "low_buy_watch":
        return "medium"
    return "low"


def _alert_reasons(item: ShortTermIntradaySentimentItem) -> list[str]:
    reasons = [signal for signal in item.signals if signal]
    if not reasons:
        reasons.append(_action_label(item.action))
    return reasons[:4]


def _alert_sort_key(alert: ShortTermIntradaySignalAlert) -> tuple[int, float, str]:
    severity_rank: dict[ShortTermAlertSeverity, int] = {"high": 0, "medium": 1, "low": 2}
    return (severity_rank[alert.severity], -(abs(alert.pct_change or 0)), alert.symbol)


def _digest_message(
    title: str,
    alerts: list[ShortTermIntradaySignalAlert],
    snapshot: ShortTermIntradaySentimentResponse,
) -> str:
    lines = [
        title,
        f"监控 {snapshot.metrics.watched_count} 只，触发提醒 {len(alerts)} 条。",
    ]
    if not alerts:
        lines.append("当前无明确盘中提醒，继续观察涨停池与炸板池变化。")
    for index, alert in enumerate(alerts, start=1):
        tags = " / ".join(alert.pool_tags[:3]) or "短线池"
        lines.append(
            f"{index}. {_action_label(alert.action)}｜{alert.name} {alert.symbol}｜"
            f"{_format_pct(alert.pct_change)}｜{tags}"
        )
        if alert.reasons:
            lines.append(f"   原因：{'；'.join(alert.reasons)}")
    lines.append("仅供复盘与盯盘，不构成投资建议。")
    return "\n".join(lines)


def _action_label(action: IntradayAction) -> str:
    labels: dict[IntradayAction, str] = {
        "watch": "观察",
        "low_buy_watch": "低吸观察",
        "reduce": "减仓确认",
        "avoid_chase": "回避追高",
        "data_incomplete": "数据不足",
    }
    return labels[action]


def _format_pct(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:+.2f}%"


def _stock_sort_key(item: ShortTermSentimentStockItem) -> tuple[int, int, str, str]:
    return (-item.board_count, -item.limit_up_hits_20d, item.first_seal_time or "99:99:99", item.symbol)


def _break_sort_key(item: ShortTermSentimentStockItem) -> tuple[int, int, str]:
    return (-item.break_board_count, -item.board_count, item.symbol)


def _empty_distribution_buckets() -> list[MarketEmotionBucket]:
    return [
        MarketEmotionBucket(label=">10%", min_pct=10, max_pct=None),
        MarketEmotionBucket(label="7-10%", min_pct=7, max_pct=10),
        MarketEmotionBucket(label="5-7%", min_pct=5, max_pct=7),
        MarketEmotionBucket(label="3-5%", min_pct=3, max_pct=5),
        MarketEmotionBucket(label="0-3%", min_pct=0, max_pct=3),
        MarketEmotionBucket(label="-3-0%", min_pct=-3, max_pct=0),
        MarketEmotionBucket(label="-5--3%", min_pct=-5, max_pct=-3),
        MarketEmotionBucket(label="-7--5%", min_pct=-7, max_pct=-5),
        MarketEmotionBucket(label="-10--7%", min_pct=-10, max_pct=-7),
        MarketEmotionBucket(label="<-10%", min_pct=None, max_pct=-10),
    ]


def _market_distribution(provider: MarketOverviewProvider) -> tuple[list[MarketEmotionBucket], StrongStockSourceStatus]:
    if not hasattr(provider, "get_pct_change_distribution"):
        return _empty_distribution_buckets(), StrongStockSourceStatus(
            source="涨跌幅分布",
            status="disabled",
            detail="当前市场概览源未提供全市场实时个股涨跌幅分布",
        )
    try:
        buckets, status = provider.get_pct_change_distribution()
    except Exception as exc:
        return _empty_distribution_buckets(), StrongStockSourceStatus(
            source="涨跌幅分布",
            status="failed",
            detail=f"全市场涨跌幅分布获取失败: {exc.__class__.__name__}",
        )
    if not buckets:
        return _empty_distribution_buckets(), status
    return buckets, status


def _seal_rate(limit_up_count: int, break_board_count: int) -> float | None:
    denominator = limit_up_count + break_board_count
    if denominator <= 0:
        return None
    return round(limit_up_count / denominator * 100, 2)


def _losing_effect_score(
    advance_count: int | None,
    decline_count: int | None,
    break_board_count: int,
    limit_down_count: int | None,
) -> float | None:
    breadth_total = (advance_count or 0) + (decline_count or 0)
    if breadth_total <= 0 and limit_down_count is None and break_board_count <= 0:
        return None
    decline_pressure = (decline_count or 0) / breadth_total * 70 if breadth_total > 0 else 0
    break_pressure = min(break_board_count * 3, 18)
    limit_down_pressure = min((limit_down_count or 0) * 0.4, 12)
    return round(min(100, decline_pressure + break_pressure + limit_down_pressure), 2)


def _market_emotion_score(
    advance_count: int | None,
    decline_count: int | None,
    limit_up_count: int,
    break_board_count: int,
    max_boards: int,
    seal_rate_pct: float | None,
    turnover_change_pct: float | None,
) -> float:
    breadth_total = (advance_count or 0) + (decline_count or 0)
    breadth_score = ((advance_count or 0) / breadth_total * 35) if breadth_total > 0 else 0
    limit_up_score = min(limit_up_count / 80 * 25, 25)
    seal_score = (seal_rate_pct or 0) / 100 * 18
    height_score = min(max_boards / 8 * 14, 14)
    turnover_score = 0
    if turnover_change_pct is not None:
        turnover_score = max(-8, min(turnover_change_pct, 8)) / 8 * 8
    break_penalty = min(break_board_count * 0.6, 10)
    score = breadth_score + limit_up_score + seal_score + height_score + turnover_score - break_penalty
    return round(max(0, min(score, 100)), 2)


def _emotion_level(score: float) -> str:
    if score < 25:
        return "冰点"
    if score < 50:
        return "一般"
    if score < 75:
        return "良好"
    return "火爆"


def _last_limit_up_date(candidate: StrongStockCandidate) -> str | None:
    for evidence in candidate.limit_up_evidence:
        if evidence.startswith("最近涨停: "):
            return evidence.removeprefix("最近涨停: ").strip() or None
    note = candidate.board_note or ""
    dates = _text_field(note, "涨停日期")
    if not dates:
        return None
    return dates.split(",")[0].strip() or None


def _limit_up_hits(candidate: StrongStockCandidate) -> int:
    for evidence in candidate.limit_up_evidence:
        if evidence.startswith("20日涨停次数: "):
            return _safe_int(evidence.removeprefix("20日涨停次数: "))
    note = candidate.board_note or ""
    dates = _text_field(note, "涨停日期")
    if dates:
        return len([date for date in dates.split(",") if date.strip()])
    return 0


def _int_field(note: str, key: str) -> int | None:
    value = _text_field(note, key)
    if value is None:
        return None
    return _safe_int(value)


def _text_field(note: str, key: str) -> str | None:
    match = re.search(rf"{re.escape(key)}\s*[:：]\s*([^;；]+)", note)
    if not match:
        return None
    return match.group(1).strip()


def _safe_int(value: object) -> int:
    match = re.search(r"-?\d+", str(value))
    if not match:
        return 0
    return int(match.group(0))


def _date_key(value: str) -> str:
    return value.replace("-", "").strip()

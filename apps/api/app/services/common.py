"""跨服务共享的小工具：去重与交易日辅助。

历史原因这些工具散落在各 provider/service 内且实现有细微差异；
此处统一语义后按模块迁移，模块内部以 `as _xxx` 别名导入保持调用点不变。
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, TypeVar

from app.models import MarketEmotionSample, MarketEmotionSnapshotResponse, StrongStockSourceStatus
from app.services.trading_calendar import is_open_session, previous_open_session

T = TypeVar("T")


def dedupe_symbols(symbols: Iterable[object]) -> list[str]:
    """保序去重股票代码：去除空白、统一大写、跳过空值。"""
    output: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = str(symbol or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def dedupe_strings(values: Iterable[str]) -> list[str]:
    """保序去重非空字符串（保留原值，不做大小写/空白归一化）。"""
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def dedupe_source_status(
    items: Iterable[StrongStockSourceStatus],
) -> list[StrongStockSourceStatus]:
    """按 (source, status, detail) 保序去重数据源状态。"""
    output: list[StrongStockSourceStatus] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.source, item.status, item.detail)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def latest_trade_date(now: datetime) -> str:
    """给定时刻对应的最近交易日（非交易日回退到前一交易日）。"""
    value = now.date()
    if not is_open_session(value):
        value = previous_open_session(value)
    return value.isoformat()


def sample_from_snapshot(snapshot: MarketEmotionSnapshotResponse) -> MarketEmotionSample:
    """把情绪快照压平成持久化样本（历史采样与盘中监控共用同一字段映射）。"""
    metrics = snapshot.metrics
    return MarketEmotionSample(
        trade_date=snapshot.trade_date,
        sampled_at=snapshot.generated_at,
        emotion_score=metrics.emotion_score,
        emotion_level=metrics.emotion_level,
        limit_up_count=metrics.limit_up_count,
        break_board_count=metrics.break_board_count,
        limit_down_count=metrics.limit_down_count,
        losing_effect_score=metrics.losing_effect_score,
        max_consecutive_boards=metrics.max_consecutive_boards,
        advance_count=metrics.advance_count,
        decline_count=metrics.decline_count,
        seal_rate_pct=metrics.seal_rate_pct,
        turnover_cny=metrics.turnover_cny,
        turnover_change_pct=metrics.turnover_change_pct,
    )

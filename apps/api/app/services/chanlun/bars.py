from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal
from zoneinfo import ZoneInfo

from app.models import KlineBar
from app.providers.tickflow import TickFlowIntradayBar


SHANGHAI = ZoneInfo("Asia/Shanghai")
PERIOD_MINUTES = {"5m": 5, "30m": 30, "60m": 60}


def normalize_intraday_bars(bars: Iterable[TickFlowIntradayBar]) -> list[TickFlowIntradayBar]:
    normalized: dict[int, TickFlowIntradayBar] = {}
    for bar in bars:
        if not _is_valid_bar(bar):
            continue
        try:
            timestamp = _from_timestamp(bar.timestamp)
        except (OverflowError, OSError, ValueError):
            continue
        if timestamp.second == 0 and timestamp.microsecond == 0 and is_a_share_trading_minute(timestamp):
            normalized[bar.timestamp] = bar
    return [normalized[timestamp] for timestamp in sorted(normalized)]


def is_a_share_trading_minute(timestamp: datetime) -> bool:
    local = to_shanghai(timestamp)
    current = local.time()
    return (
        (current.hour == 9 and current.minute >= 30)
        or current.hour == 10
        or (current.hour == 11 and current.minute < 30)
        or current.hour == 13
        or current.hour == 14
    )


def aggregate_closed_intraday_bars(
    bars: Iterable[TickFlowIntradayBar],
    *,
    period: Literal["5m", "30m", "60m"],
    now: datetime,
) -> list[KlineBar]:
    period_minutes = PERIOD_MINUTES[period]
    cutoff = to_shanghai(now)
    buckets: dict[datetime, list[tuple[datetime, TickFlowIntradayBar]]] = {}

    for bar in normalize_intraday_bars(bars):
        timestamp = _from_timestamp(bar.timestamp)
        if timestamp > cutoff:
            continue
        bucket_start = intraday_bucket_start(timestamp, period)
        buckets.setdefault(bucket_start, []).append((timestamp, bar))

    result: list[KlineBar] = []
    for bucket_start in sorted(buckets):
        bucket_close = bucket_start + timedelta(minutes=period_minutes)
        bucket = buckets[bucket_start]
        if bucket_close > cutoff or not _bucket_is_usable(bucket, bucket_start, period_minutes):
            continue
        ordered_bars = [bar for _, bar in bucket]
        result.append(
            KlineBar(
                date=bucket_close.isoformat(timespec="seconds"),
                open=ordered_bars[0].open,
                close=ordered_bars[-1].close,
                high=max(bar.high for bar in ordered_bars),
                low=min(bar.low for bar in ordered_bars),
                volume=sum(bar.volume for bar in ordered_bars),
                amount=sum(bar.amount for bar in ordered_bars),
            )
        )
    return result


def to_shanghai(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=SHANGHAI)
    return timestamp.astimezone(SHANGHAI)


def _from_timestamp(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp / 1000, tz=SHANGHAI)


def _is_valid_bar(bar: TickFlowIntradayBar) -> bool:
    values = (bar.open, bar.high, bar.low, bar.close, bar.volume, bar.amount)
    if not all(isfinite(value) for value in values):
        return False
    if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
        return False
    if bar.volume < 0 or bar.amount < 0:
        return False
    return bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close)


def session_start(timestamp: datetime) -> datetime:
    if timestamp.hour < 12:
        return timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
    return timestamp.replace(hour=13, minute=0, second=0, microsecond=0)


def intraday_bucket_start(timestamp: datetime, period: Literal["5m", "30m", "60m"]) -> datetime:
    local = to_shanghai(timestamp)
    start = session_start(local)
    period_minutes = PERIOD_MINUTES[period]
    elapsed_minutes = int((local - start).total_seconds() // 60)
    return start + timedelta(minutes=(elapsed_minutes // period_minutes) * period_minutes)


def _bucket_is_usable(
    bucket: list[tuple[datetime, TickFlowIntradayBar]],
    bucket_start: datetime,
    period_minutes: int,
) -> bool:
    """桶内分钟必须是自 bucket_start 起连续的前缀（允许尾部缺分钟，不允许中间空洞）。

    缺失的分钟仍会由 coverage 审计计入 missing_minutes，从而阻止基于该数据的
    分析被判定为 complete；此处只在展示 K 线时避免因单分钟缺失丢掉整个桶造成空洞。
    """
    if not bucket or len(bucket) > period_minutes:
        return False
    expected = bucket_start
    for timestamp, _ in bucket:
        if timestamp != expected:
            return False
        expected += timedelta(minutes=1)
    return True

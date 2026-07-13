from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal
from zoneinfo import ZoneInfo

from app.models import KlineBar
from app.providers.tickflow import TickFlowIntradayBar


SHANGHAI = ZoneInfo("Asia/Shanghai")
_PERIOD_MINUTES = {"5m": 5, "30m": 30, "60m": 60}


def normalize_intraday_bars(bars: Iterable[TickFlowIntradayBar]) -> list[TickFlowIntradayBar]:
    normalized: dict[int, TickFlowIntradayBar] = {}
    for bar in bars:
        if not _is_valid_bar(bar):
            continue
        try:
            timestamp = _from_timestamp(bar.timestamp)
        except (OverflowError, OSError, ValueError):
            continue
        if is_a_share_trading_minute(timestamp):
            normalized[bar.timestamp] = bar
    return [normalized[timestamp] for timestamp in sorted(normalized)]


def is_a_share_trading_minute(timestamp: datetime) -> bool:
    local = _to_shanghai(timestamp)
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
    period_minutes = _PERIOD_MINUTES[period]
    cutoff = _to_shanghai(now)
    buckets: dict[datetime, list[tuple[datetime, TickFlowIntradayBar]]] = {}

    for bar in normalize_intraday_bars(bars):
        timestamp = _from_timestamp(bar.timestamp)
        if timestamp > cutoff:
            continue
        session_start = _session_start(timestamp)
        elapsed_minutes = int((timestamp - session_start).total_seconds() // 60)
        bucket_start = session_start + timedelta(minutes=(elapsed_minutes // period_minutes) * period_minutes)
        buckets.setdefault(bucket_start, []).append((timestamp, bar))

    result: list[KlineBar] = []
    for bucket_start in sorted(buckets):
        bucket_close = bucket_start + timedelta(minutes=period_minutes)
        bucket = buckets[bucket_start]
        if bucket_close > cutoff or not _is_complete_bucket(bucket, bucket_start, period_minutes):
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


def _to_shanghai(timestamp: datetime) -> datetime:
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


def _session_start(timestamp: datetime) -> datetime:
    if timestamp.hour < 12:
        return timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
    return timestamp.replace(hour=13, minute=0, second=0, microsecond=0)


def _is_complete_bucket(
    bucket: list[tuple[datetime, TickFlowIntradayBar]],
    bucket_start: datetime,
    period_minutes: int,
) -> bool:
    if len(bucket) != period_minutes:
        return False
    return all(
        timestamp == bucket_start + timedelta(minutes=index)
        for index, (timestamp, _) in enumerate(bucket)
    )

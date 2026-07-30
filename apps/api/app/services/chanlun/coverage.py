from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Literal

from app.models import ChanlunCoverage
from app.services.chanlun.bars import (
    PERIOD_MINUTES,
    SHANGHAI,
    intraday_bucket_start,
    is_a_share_trading_minute,
    to_shanghai,
)
from app.services.trading_calendar import is_open_session


IntradayPeriod = Literal["5m", "30m", "60m"]
_SESSION_MINUTES = 240
_TDX_PAGE_SIZE = 800


def required_intraday_raw_minutes(period: IntradayPeriod, lookback: int) -> int:
    if lookback < 0:
        raise ValueError("lookback must be non-negative")
    return lookback * PERIOD_MINUTES[period] + 5 * _SESSION_MINUTES


def round_intraday_fetch_count(raw_minutes: int, page_size: int = _TDX_PAGE_SIZE) -> int:
    if raw_minutes < 0:
        raise ValueError("raw_minutes must be non-negative")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    return ((raw_minutes + page_size - 1) // page_size) * page_size


def open_sessions_in_calendar_window(history_days: int, *, now: datetime) -> int:
    if history_days < 0:
        raise ValueError("history_days must be non-negative")
    current_date = to_shanghai(now).date()
    return sum(
        is_open_session(current_date - timedelta(days=offset))
        for offset in range(history_days)
    )


def audit_intraday_coverage(
    timestamps: Iterable[str],
    *,
    period: IntradayPeriod,
    lookback: int,
    now: datetime,
    expected_trade_dates: set[date] | None,
) -> ChanlunCoverage:
    cutoff = to_shanghai(now)
    normalized = _normalized_trading_minutes(timestamps)
    required_raw_minutes = required_intraday_raw_minutes(period, lookback)

    if expected_trade_dates is None:
        return ChanlunCoverage(
            status="unverified",
            required_period_bars=lookback,
            available_period_bars=0,
            required_raw_minutes=required_raw_minutes,
            available_raw_minutes=len(normalized),
            earliest_at=_iso_or_none(normalized, first=True),
            latest_at=_iso_or_none(normalized, first=False),
            reason="缺少标的交易日参考，无法验证跨日连续性",
            backfill_required=True,
        )

    expected_by_date = {
        session_date: _expected_session_minutes(session_date, period, cutoff)
        for session_date in expected_trade_dates
        if is_open_session(session_date) and session_date <= cutoff.date()
    }
    expected_minutes = set().union(*expected_by_date.values()) if expected_by_date else set()
    available_minutes = normalized & expected_minutes
    expected_buckets = _expected_buckets(expected_minutes, period, cutoff)
    complete_bucket_count = sum(
        expected <= available_minutes for expected in expected_buckets.values()
    )
    missing_minutes = len(expected_minutes - available_minutes)
    incomplete_sessions = sum(
        not expected <= available_minutes
        for expected in expected_by_date.values()
        if expected
    ) + _separated_session_gaps(expected_by_date)
    complete_sessions = sum(
        bool(expected) and expected <= available_minutes
        for expected in expected_by_date.values()
    )
    status = (
        "complete"
        if complete_bucket_count >= lookback and missing_minutes == 0 and incomplete_sessions == 0
        else "incomplete"
    )

    return ChanlunCoverage(
        status=status,
        required_period_bars=lookback,
        available_period_bars=complete_bucket_count,
        required_raw_minutes=required_raw_minutes,
        available_raw_minutes=len(available_minutes),
        complete_sessions=complete_sessions,
        incomplete_sessions=incomplete_sessions,
        missing_minutes=missing_minutes,
        earliest_at=_iso_or_none(available_minutes, first=True),
        latest_at=_iso_or_none(available_minutes, first=False),
        reason=_coverage_reason(status, complete_bucket_count, lookback, missing_minutes, incomplete_sessions),
        backfill_required=status != "complete" or complete_bucket_count < lookback,
    )


def _normalized_trading_minutes(timestamps: Iterable[str]) -> set[datetime]:
    normalized: set[datetime] = set()
    for raw_timestamp in timestamps:
        try:
            timestamp = to_shanghai(datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")))
        except ValueError:
            continue
        if timestamp.second == 0 and timestamp.microsecond == 0 and is_a_share_trading_minute(timestamp):
            normalized.add(timestamp)
    return normalized


def _expected_session_minutes(
    session_date: date, period: IntradayPeriod, cutoff: datetime
) -> set[datetime]:
    starts = (
        datetime.combine(session_date, datetime.min.time(), tzinfo=SHANGHAI).replace(hour=9, minute=30),
        datetime.combine(session_date, datetime.min.time(), tzinfo=SHANGHAI).replace(hour=13),
    )
    return {
        start + timedelta(minutes=offset)
        for start in starts
        for offset in range(120)
        if intraday_bucket_start(start + timedelta(minutes=offset), period)
        + timedelta(minutes=PERIOD_MINUTES[period])
        <= cutoff
    }


def _expected_buckets(
    expected_minutes: set[datetime], period: IntradayPeriod, cutoff: datetime
) -> dict[datetime, set[datetime]]:
    buckets: dict[datetime, set[datetime]] = {}
    for timestamp in expected_minutes:
        bucket_start = intraday_bucket_start(timestamp, period)
        if bucket_start + timedelta(minutes=PERIOD_MINUTES[period]) <= cutoff:
            buckets.setdefault(bucket_start, set()).add(timestamp)
    return buckets


def _separated_session_gaps(expected_by_date: dict[date, set[datetime]]) -> int:
    session_dates = sorted(session_date for session_date, minutes in expected_by_date.items() if minutes)
    return sum(
        any(
            is_open_session(candidate)
            for candidate in _dates_between(previous, current)
        )
        for previous, current in zip(session_dates, session_dates[1:])
    )


def _dates_between(previous: date, current: date) -> Iterable[date]:
    candidate = previous + timedelta(days=1)
    while candidate < current:
        yield candidate
        candidate += timedelta(days=1)


def _iso_or_none(timestamps: set[datetime], *, first: bool) -> str | None:
    if not timestamps:
        return None
    timestamp = min(timestamps) if first else max(timestamps)
    return timestamp.isoformat(timespec="seconds")


def _coverage_reason(
    status: Literal["complete", "incomplete"],
    available_period_bars: int,
    lookback: int,
    missing_minutes: int,
    incomplete_sessions: int,
) -> str:
    if status == "complete":
        return "分钟历史完整"
    if missing_minutes or incomplete_sessions:
        return "分钟历史存在缺口"
    if available_period_bars < lookback:
        return "已闭合周期数量不足"
    return "分钟历史不完整"

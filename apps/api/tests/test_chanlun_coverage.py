from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.chanlun.coverage import (
    audit_intraday_coverage,
    open_sessions_in_calendar_window,
    required_intraday_raw_minutes,
    round_intraday_fetch_count,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def shanghai(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SHANGHAI)


def full_session(value: str) -> list[str]:
    day = date.fromisoformat(value)
    starts = (
        datetime.combine(day, datetime.min.time(), tzinfo=SHANGHAI).replace(hour=9, minute=30),
        datetime.combine(day, datetime.min.time(), tzinfo=SHANGHAI).replace(hour=13),
    )
    return [
        (start + timedelta(minutes=index)).isoformat()
        for start in starts
        for index in range(120)
    ]


def test_two_sessions_with_a_28_day_trading_gap_are_incomplete() -> None:
    timestamps = full_session("2026-06-01") + full_session("2026-06-29")

    result = audit_intraday_coverage(
        timestamps,
        period="5m",
        lookback=96,
        now=shanghai("2026-06-29 15:05"),
        expected_trade_dates={date(2026, 6, 1), date(2026, 6, 29)},
    )

    assert result.status == "incomplete"
    assert result.incomplete_sessions == 1
    assert result.backfill_required is True


def test_220_60m_bars_require_14400_raw_minutes() -> None:
    assert required_intraday_raw_minutes("60m", 220) == 14400
    assert round_intraday_fetch_count(14400) == 14400


def test_missing_one_minute_does_not_cross_a_5m_bucket() -> None:
    timestamps = full_session("2026-07-10")
    timestamps.remove(shanghai("2026-07-10 14:32").isoformat())

    result = audit_intraday_coverage(
        timestamps,
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.status == "incomplete"
    assert result.missing_minutes == 1


@pytest.mark.parametrize(
    ("period", "lookback"),
    [("5m", 6), ("30m", 3), ("60m", 2)],
)
def test_trailing_window_ignores_older_missing_minutes(
    period: str, lookback: int
) -> None:
    older = full_session("2026-07-09")
    older.remove(shanghai("2026-07-09 09:32").isoformat())

    result = audit_intraday_coverage(
        older + full_session("2026-07-10"),
        period=period,  # type: ignore[arg-type]
        lookback=lookback,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 9), date(2026, 7, 10)},
    )

    assert result.status == "complete"
    assert result.available_period_bars == lookback
    assert result.missing_minutes == 0
    assert result.incomplete_sessions == 0


@pytest.mark.parametrize(
    ("period", "lookback", "missing_at"),
    [("5m", 6, "14:32"), ("30m", 3, "14:02"), ("60m", 2, "14:02")],
)
def test_trailing_window_still_rejects_a_missing_minute(
    period: str, lookback: int, missing_at: str
) -> None:
    timestamps = full_session("2026-07-10")
    timestamps.remove(shanghai(f"2026-07-10 {missing_at}").isoformat())

    result = audit_intraday_coverage(
        timestamps,
        period=period,  # type: ignore[arg-type]
        lookback=lookback,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.status == "incomplete"
    assert result.missing_minutes == 1
    assert result.incomplete_sessions == 1


def test_current_open_bucket_does_not_count_as_missing_minutes() -> None:
    start = shanghai("2026-07-10 09:30")
    timestamps = [(start + timedelta(minutes=index)).isoformat() for index in range(32)]

    result = audit_intraday_coverage(
        timestamps,
        period="5m",
        lookback=6,
        now=shanghai("2026-07-10 10:02"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.status == "complete"
    assert result.available_period_bars == 6
    assert result.missing_minutes == 0
    assert result.incomplete_sessions == 0


def test_complete_day_has_no_lunch_gap() -> None:
    result = audit_intraday_coverage(
        full_session("2026-07-10"),
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.status == "complete"
    assert result.missing_minutes == 0
    assert result.available_period_bars == 20


def test_duplicate_timestamps_do_not_inflate_available_raw_minutes() -> None:
    timestamps = full_session("2026-07-10")

    result = audit_intraday_coverage(
        [*timestamps, timestamps[0], timestamps[-1]],
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates={date(2026, 7, 10)},
    )

    assert result.available_raw_minutes == 100


def test_missing_trade_date_reference_is_unverified() -> None:
    result = audit_intraday_coverage(
        full_session("2026-07-10"),
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates=None,
    )

    assert result.status == "unverified"
    assert result.backfill_required is True


def test_unverified_coverage_excludes_future_minutes() -> None:
    current = full_session("2026-07-10")
    future = shanghai("2026-07-11 09:30").isoformat()

    result = audit_intraday_coverage(
        [*current, future],
        period="5m",
        lookback=20,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates=None,
    )

    assert result.status == "unverified"
    assert result.available_raw_minutes == 240
    assert result.earliest_at == "2026-07-10T09:30:00+08:00"
    assert result.latest_at == "2026-07-10T14:59:00+08:00"


def test_unrepresentable_timestamp_is_ignored() -> None:
    result = audit_intraday_coverage(
        [
            shanghai("2026-07-10 09:30").isoformat(),
            "9999-12-31T23:59:00-14:00",
        ],
        period="5m",
        lookback=1,
        now=shanghai("2026-07-10 15:05"),
        expected_trade_dates=None,
    )

    assert result.available_raw_minutes == 1
    assert result.earliest_at == "2026-07-10T09:30:00+08:00"
    assert result.latest_at == "2026-07-10T09:30:00+08:00"


def test_fetch_count_rounds_up_to_the_tdx_page_size() -> None:
    assert round_intraday_fetch_count(801) == 1600


def test_calendar_window_counts_open_sessions() -> None:
    assert open_sessions_in_calendar_window(3, now=shanghai("2026-07-13 15:05")) == 1

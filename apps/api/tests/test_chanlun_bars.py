from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.providers.tickflow import TickFlowIntradayBar
from app.services.chanlun.bars import (
    aggregate_closed_intraday_bars,
    is_a_share_trading_minute,
    normalize_intraday_bars,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")


def shanghai(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=SHANGHAI)


def minute_bar(value: str, *, close: float = 10.0, open: float | None = None) -> TickFlowIntradayBar:
    timestamp = shanghai(value)
    return TickFlowIntradayBar(
        timestamp=int(timestamp.timestamp() * 1000),
        open=close if open is None else open,
        high=close + 0.2,
        low=close - 0.2,
        close=close,
        volume=100.0,
        amount=1_000.0,
    )


def minute_bars(*values: str) -> list[TickFlowIntradayBar]:
    return [minute_bar(value, close=10.0 + index) for index, value in enumerate(values)]


def session_bars(*, now: datetime) -> list[TickFlowIntradayBar]:
    morning_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    afternoon_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
    bars: list[TickFlowIntradayBar] = []
    current = morning_start
    while current < now and current.time() < datetime.strptime("11:30", "%H:%M").time():
        bars.append(minute_bar(current.isoformat(), close=10.0 + len(bars)))
        current += timedelta(minutes=1)
    current = afternoon_start
    while current < now and current.time() < datetime.strptime("15:00", "%H:%M").time():
        bars.append(minute_bar(current.isoformat(), close=10.0 + len(bars)))
        current += timedelta(minutes=1)
    return bars


def test_aggregate_5m_never_crosses_lunch_break() -> None:
    bars = minute_bars(
        "2026-07-10 11:28",
        "2026-07-10 11:29",
        "2026-07-10 13:00",
        "2026-07-10 13:01",
    )

    result = aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 13:03"))

    assert result == []


def test_unclosed_bucket_is_excluded_from_confirmed_bars() -> None:
    bars = minute_bars("2026-07-10 09:30", "2026-07-10 09:31", "2026-07-10 09:32")

    assert aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 09:33")) == []


@pytest.mark.parametrize(
    ("period", "bar_count", "cutoff"),
    [("30m", 29, "10:00"), ("60m", 59, "10:30")],
)
def test_aggregate_excludes_incomplete_long_period_bucket(
    period: str,
    bar_count: int,
    cutoff: str,
) -> None:
    start = shanghai("2026-07-10 09:30")
    bars = [
        minute_bar((start + timedelta(minutes=index)).isoformat())
        for index in range(bar_count)
    ]

    assert aggregate_closed_intraday_bars(
        bars,
        period=period,  # type: ignore[arg-type]
        now=shanghai(f"2026-07-10 {cutoff}"),
    ) == []


def test_complete_bucket_uses_last_close_and_close_label() -> None:
    bars = minute_bars(
        "2026-07-10 09:30",
        "2026-07-10 09:31",
        "2026-07-10 09:32",
        "2026-07-10 09:33",
        "2026-07-10 09:34",
    )

    result = aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 09:35"))

    assert result[0].date == "2026-07-10T09:35:00+08:00"
    assert result[0].close == bars[-1].close


@pytest.mark.parametrize(
    ("period", "cutoff", "expected_labels"),
    [
        ("30m", "10:00", ["10:00"]),
        ("30m", "10:30", ["10:00", "10:30"]),
        ("30m", "11:30", ["10:00", "10:30", "11:00", "11:30"]),
        ("30m", "13:30", ["10:00", "10:30", "11:00", "11:30", "13:30"]),
        ("30m", "15:00", ["10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00"]),
        ("60m", "10:00", []),
        ("60m", "10:30", ["10:30"]),
        ("60m", "11:30", ["10:30", "11:30"]),
        ("60m", "13:30", ["10:30", "11:30"]),
        ("60m", "15:00", ["10:30", "11:30", "14:00", "15:00"]),
    ],
)
def test_aggregate_period_endpoints(
    period: str,
    cutoff: str,
    expected_labels: list[str],
) -> None:
    now = shanghai(f"2026-07-10 {cutoff}")

    result = aggregate_closed_intraday_bars(session_bars(now=now), period=period, now=now)

    assert [bar.date[11:16] for bar in result] == expected_labels


def test_normalize_converts_to_shanghai_sorts_and_keeps_final_duplicate() -> None:
    utc_0930 = datetime(2026, 7, 10, 1, 30, tzinfo=UTC)
    first = TickFlowIntradayBar(
        timestamp=int(utc_0930.timestamp() * 1000),
        open=10.0,
        high=10.2,
        low=9.8,
        close=10.0,
        volume=100.0,
        amount=1_000.0,
    )
    replacement = first.model_copy(update={"close": 10.8, "high": 11.0})
    later = minute_bar("2026-07-10 09:31", close=11.0)

    result = normalize_intraday_bars([later, first, replacement])

    assert [bar.timestamp for bar in result] == [first.timestamp, later.timestamp]
    assert result[0].close == 10.8
    assert is_a_share_trading_minute(datetime.fromtimestamp(result[0].timestamp / 1000, tz=UTC))


def test_normalize_removes_invalid_and_out_of_session_bars() -> None:
    invalid = minute_bar("2026-07-10 09:30", close=0.0)
    before_open = minute_bar("2026-07-10 09:29", close=10.0)
    after_close = minute_bar("2026-07-10 15:00", close=10.0)
    valid = minute_bar("2026-07-10 13:00", close=10.0)

    assert normalize_intraday_bars([invalid, before_open, after_close, valid]) == [valid]


def test_aggregate_excludes_future_input() -> None:
    bars = minute_bars(
        "2026-07-10 09:30",
        "2026-07-10 09:31",
        "2026-07-10 09:32",
        "2026-07-10 09:33",
        "2026-07-10 09:34",
        "2026-07-10 09:40",
    )

    result = aggregate_closed_intraday_bars(bars, period="5m", now=shanghai("2026-07-10 09:35"))

    assert len(result) == 1
    assert result[0].close == bars[4].close

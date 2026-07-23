from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import EtfSharePoint
from app.services.etf_excess_flow import build_activity_metrics, build_flow_trend


def _history_with_deltas(
    symbol: str,
    deltas: list[float],
    *,
    close: float | None = 4.0,
) -> list[EtfSharePoint]:
    start = date(2026, 5, 4)
    total_shares = 1_000_000.0
    rows = [
        EtfSharePoint(
            trade_date=start.isoformat(),
            symbol=symbol,
            total_shares=total_shares,
            close=close,
        )
    ]
    current_date = start
    for delta in deltas:
        current_date += timedelta(days=1)
        next_date = current_date
        while next_date.weekday() >= 5:
            next_date += timedelta(days=1)
        current_date = next_date
        total_shares += delta
        rows.append(
            EtfSharePoint(
                trade_date=next_date.isoformat(),
                symbol=symbol,
                total_shares=total_shares,
                close=close,
            )
        )
    return rows


def test_share_change_multiple_excludes_current_day_and_marks_tenfold() -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [1000])

    current = build_activity_metrics(history, symbols=("510050.SH",)).items[-1]

    assert current.share_change_20d_avg_abs == 100
    assert current.share_change_20d_multiple == 10
    assert current.is_tenfold_share_change is True
    assert current.multiple is None
    assert current.is_tenfold is False
    assert current.share_change_direction == "increase"


@pytest.mark.parametrize(
    ("delta", "direction"),
    [(-1000, "decrease"), (999, "increase")],
)
def test_tenfold_boundary_preserves_direction_and_requires_at_least_ten(
    delta: float,
    direction: str,
) -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [delta])

    current = build_activity_metrics(history, symbols=("510050.SH",)).items[-1]

    assert current.share_change_direction == direction
    assert current.is_tenfold_share_change is (abs(delta) >= 1000)


def test_insufficient_history_does_not_create_twenty_day_multiple() -> None:
    history = _history_with_deltas("510050.SH", [100] * 19 + [1000])

    current = build_activity_metrics(history, symbols=("510050.SH",)).items[-1]

    assert current.share_change_20d_avg_abs is None
    assert current.share_change_20d_multiple is None
    assert current.is_tenfold_share_change is False


def test_zero_baseline_does_not_create_infinite_multiple() -> None:
    history = _history_with_deltas("510050.SH", [0] * 20 + [1000])

    current = build_activity_metrics(history, symbols=("510050.SH",)).items[-1]

    assert current.share_change_20d_avg_abs == 0
    assert current.share_change_20d_multiple is None
    assert current.is_tenfold_share_change is False


def test_missing_observed_trade_date_does_not_turn_cumulative_change_into_daily_change() -> None:
    primary = _history_with_deltas("510050.SH", [100] * 20 + [1000])
    companion = _history_with_deltas("510300.SH", [100] * 20 + [1000])
    missing = primary.pop(5).trade_date

    items = build_activity_metrics([*primary, *companion], symbols=("510050.SH", "510300.SH")).items

    assert all(item.trade_date != missing for item in items if item.symbol == "510050.SH")
    after_gap = next(item for item in items if item.symbol == "510050.SH" and item.trade_date > missing)
    assert after_gap.share_delta is None
    assert after_gap.share_change_20d_multiple is None


def test_flow_trend_aggregates_events_and_keeps_symbol_order_stable() -> None:
    history = [
        *_history_with_deltas("510300.SH", [100] * 20 + [1000], close=4.0),
        *_history_with_deltas("510050.SH", [-50] * 20 + [-500], close=2.0),
    ]

    point = build_flow_trend(
        history,
        symbols=("510300.SH", "510050.SH"),
    ).points[-1]

    assert point.net_excess_flow_cny == pytest.approx(2700)
    assert point.excess_inflow_cny == pytest.approx(3600)
    assert point.excess_outflow_cny == pytest.approx(900)
    assert point.coverage_count == 2
    assert point.expected_count == 2
    assert point.tenfold_increase_count == 1
    assert point.tenfold_decrease_count == 1
    assert point.trigger_symbols == ["510050.SH", "510300.SH"]


def test_missing_close_is_excluded_from_money_coverage_not_treated_as_zero() -> None:
    history = [
        *_history_with_deltas("510050.SH", [100] * 20 + [1000], close=4.0),
        *_history_with_deltas("510300.SH", [100] * 20 + [1000], close=None),
    ]

    point = build_flow_trend(
        history,
        symbols=("510050.SH", "510300.SH"),
    ).points[-1]

    assert point.coverage_count == 1
    assert point.expected_count == 2
    assert point.net_excess_flow_cny == pytest.approx(3600)


def test_flow_trend_returns_null_money_when_no_price_is_available() -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [1000], close=None)

    point = build_flow_trend(history, symbols=("510050.SH",)).points[-1]

    assert point.coverage_count == 0
    assert point.net_excess_flow_cny is None
    assert point.excess_inflow_cny is None
    assert point.excess_outflow_cny is None


@pytest.mark.parametrize("close", [0.0, -1.0])
def test_non_positive_close_is_excluded_from_money_coverage(close: float) -> None:
    history = _history_with_deltas("510050.SH", [100] * 20 + [1000], close=close)

    point = build_flow_trend(history, symbols=("510050.SH",)).points[-1]

    assert point.coverage_count == 0
    assert point.net_excess_flow_cny is None
